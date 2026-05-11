import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_bluetooth_serial/flutter_bluetooth_serial.dart';
import 'package:permission_handler/permission_handler.dart';

void main() {
  runApp(const RobotControlApp());
}

class RobotControlApp extends StatelessWidget {
  const RobotControlApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'STM32 Advanced Controller',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFB3C8CF),
          brightness: Brightness.light,
        ),
      ),
      home: const UnifiedControlScreen(),
    );
  }
}

class UnifiedControlScreen extends StatefulWidget {
  const UnifiedControlScreen({super.key});

  @override
  State<UnifiedControlScreen> createState() => _UnifiedControlScreenState();
}

class _UnifiedControlScreenState extends State<UnifiedControlScreen> {
  List<BluetoothDevice> _devicesList = [];
  BluetoothDevice? _selectedDevice;
  BluetoothConnection? _connection;
  bool _isConnecting = false;
  bool _isScanning = false;
  StreamSubscription<BluetoothDiscoveryResult>? _discoveryStreamSubscription;
  bool get _isConnected => (_connection?.isConnected ?? false);

  int _leftPwm = 0;
  int _rightPwm = 0;
  DateTime? _lastSendTime;
  final int _throttleMs = 50;

  int _controlMode = 0; // 0: Slider, 1: Button, 2: Tracking
  int _trackingState = 0; // 0: Idle, 1: Active

  @override
  void initState() {
    super.initState();
    _initBluetooth();
  }

  Future<void> _initBluetooth() async {
    await [Permission.bluetooth, Permission.bluetoothScan, Permission.bluetoothConnect, Permission.location].request();
    _loadBondedDevices();
  }

  Future<void> _loadBondedDevices() async {
    try {
      List<BluetoothDevice> bondedDevices = await FlutterBluetoothSerial.instance.getBondedDevices();
      setState(() {
        for (var device in bondedDevices) {
          if (!_devicesList.any((d) => d.address == device.address)) _devicesList.add(device);
        }
        if (_selectedDevice == null && _devicesList.isNotEmpty) _selectedDevice = _devicesList.first;
      });
    } catch (e) { debugPrint("로드 에러: $e"); }
  }

  void _startDiscovery() {
    if (_isScanning) return;
    setState(() { _isScanning = true; _devicesList.removeWhere((d) => !d.isBonded); });
    _discoveryStreamSubscription = FlutterBluetoothSerial.instance.startDiscovery().listen((r) {
      setState(() { if (!_devicesList.any((d) => d.address == r.device.address)) _devicesList.add(r.device); });
    });
    _discoveryStreamSubscription?.onDone(() { if (mounted) setState(() => _isScanning = false); });
  }

  Future<void> _toggleConnection() async {
    if (_isConnected) { await _connection?.close(); setState(() => _connection = null); return; }
    if (_selectedDevice == null) return;
    setState(() => _isConnecting = true);
    try {
      _connection = await BluetoothConnection.toAddress(_selectedDevice!.address);
      _connection!.input!.listen((data) {}).onDone(() { if (mounted) setState(() => _connection = null); });
      _sendControlData(0, 0);
    } catch (e) { debugPrint('연결 실패: $e'); }
    finally { if (mounted) setState(() => _isConnecting = false); }
  }

  void _sendControlData(int leftSpeed, int rightSpeed) {
    if (_controlMode != 2) {
      final now = DateTime.now();
      if (_lastSendTime != null && now.difference(_lastSendTime!).inMilliseconds < _throttleMs) return;
      _lastSendTime = now;
    }

    int modeFlag = (_controlMode == 2 && _trackingState == 1) ? 1 : 0;
    int lDir = leftSpeed >= 0 ? 0 : 1;
    int rDir = rightSpeed >= 0 ? 0 : 1;
    int lPwm = leftSpeed.abs().clamp(0, 255);
    int rPwm = rightSpeed.abs().clamp(0, 255);

    Uint8List packet = Uint8List.fromList([0xAA, modeFlag, lDir, lPwm, rDir, rPwm, 0x55]);

    // [디버깅 출력] 블루투스 연결 여부와 상관없이 콘솔에 찍힘
    String hexPacket = packet.map((b) => '0x${b.toRadixString(16).padLeft(2, '0').toUpperCase()}').join(', ');
    debugPrint("[Mode: $_controlMode] Packet: [$hexPacket] (L:$leftSpeed, R:$rightSpeed)");

    if (_isConnected && _connection != null) {
      try {
        _connection!.output.add(packet);
        _connection!.output.allSent;
      } catch (e) { debugPrint("전송 오류: $e"); }
    }
  }

  @override
  void dispose() {
    _discoveryStreamSubscription?.cancel();
    _connection?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(width: 12, height: 12, decoration: BoxDecoration(shape: BoxShape.circle, color: _isConnected ? Colors.green : Colors.red)),
            const SizedBox(width: 10),
            const Text('Tracking Robot Controller'),
          ],
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            _buildConnectionCard(colorScheme),
            const SizedBox(height: 20),
            _buildModeToggle(colorScheme),
            Expanded(child: _buildCurrentModeUI()),
            _buildEmergencyStop(),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildConnectionCard(ColorScheme colorScheme) {
    return Card(
      elevation: 0, color: Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Row(
          children: [
            Expanded(child: DropdownButtonHideUnderline(child: DropdownButton<BluetoothDevice>(isExpanded: true, value: _selectedDevice, items: _devicesList.map((d) => DropdownMenuItem(value: d, child: Text(d.name ?? d.address))).toList(), onChanged: _isConnected ? null : (val) => setState(() => _selectedDevice = val)))),
            IconButton(icon: Icon(_isScanning ? Icons.sync : Icons.search), onPressed: (_isConnected || _isScanning) ? null : _startDiscovery),
            ElevatedButton(onPressed: _isConnecting ? null : _toggleConnection, child: Text(_isConnected ? '해제' : '연결')),
          ],
        ),
      ),
    );
  }

  Widget _buildModeToggle(ColorScheme colorScheme) {
    return SegmentedButton<int>(
      segments: const [
        ButtonSegment(value: 0, label: Text('Slider'), icon: Icon(Icons.linear_scale)),
        ButtonSegment(value: 1, label: Text('Button'), icon: Icon(Icons.apps)),
        ButtonSegment(value: 2, label: Text('Tracking'), icon: Icon(Icons.center_focus_strong)),
      ],
      selected: {_controlMode},
      onSelectionChanged: (val) {
        setState(() {
          _controlMode = val.first;
          // 팩트체크: 모드 변경 시 값을 0으로 리셋하여 안전 보장
          _leftPwm = 0;
          _rightPwm = 0;
          _trackingState = 0;
        });
        _sendControlData(0, 0); // 즉시 정지 패킷 전송
      },
    );
  }

  Widget _buildCurrentModeUI() {
    if (_controlMode == 0) return _buildSliderUI();
    if (_controlMode == 1) return _buildButtonUI();
    return _buildTrackingUI();
  }

  Widget _buildSliderUI() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        _buildSingleVerticalSlider("LEFT", _leftPwm, (val) { setState(() => _leftPwm = val.toInt()); _sendControlData(_leftPwm, _rightPwm); }),
        _buildSingleVerticalSlider("RIGHT", _rightPwm, (val) { setState(() => _rightPwm = val.toInt()); _sendControlData(_leftPwm, _rightPwm); }),
      ],
    );
  }

  Widget _buildSingleVerticalSlider(String label, int value, ValueChanged<double> onChanged) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(label),
        const SizedBox(height: 10),
        Container(
          height: 250, decoration: BoxDecoration(color: Colors.grey.shade100, borderRadius: BorderRadius.circular(30)),
          child: RotatedBox(
            quarterTurns: 3,
            child: Slider(
              value: value.toDouble(), min: -255, max: 255,
              onChanged: onChanged,
              // 팩트체크: 여기서 onChanged(0)를 호출하던 onChangeEnd를 삭제하여 값 유지
              onChangeEnd: null,
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text("$value"),
      ],
    );
  }

  Widget _buildButtonUI() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _buildDirectionButton(Icons.keyboard_arrow_up, 255, 255),
        const SizedBox(height: 20),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [_buildDirectionButton(Icons.keyboard_arrow_left, -200, 200), const SizedBox(width: 80), _buildDirectionButton(Icons.keyboard_arrow_right, 200, -200)]),
        const SizedBox(height: 20),
        _buildDirectionButton(Icons.keyboard_arrow_down, -255, -255),
      ],
    );
  }

  Widget _buildDirectionButton(IconData icon, int l, int r) {
    return GestureDetector(
      onTapDown: (_) => _sendControlData(l, r),
      onTapUp: (_) => _sendControlData(0, 0),
      onTapCancel: () => _sendControlData(0, 0),
      child: Container(width: 75, height: 75, decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 10)]), child: Icon(icon, size: 40)),
    );
  }

  Widget _buildTrackingUI() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.visibility, size: 60),
        const SizedBox(height: 40),
        ElevatedButton.icon(
          onPressed: () { setState(() => _trackingState = _trackingState == 0 ? 1 : 0); _sendControlData(0, 0); },
          icon: Icon(_trackingState == 0 ? Icons.play_arrow : Icons.pause),
          label: Text(_trackingState == 0 ? "트래킹 시작" : "트래킹 일시정지"),
        ),
      ],
    );
  }

  Widget _buildEmergencyStop() {
    return SizedBox(
      width: double.infinity, height: 60,
      child: ElevatedButton(
        onPressed: () { setState(() { _leftPwm = 0; _rightPwm = 0; _controlMode = 0; _trackingState = 0; }); _sendControlData(0, 0); },
        style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFFFE5E5), foregroundColor: Colors.red),
        child: const Text("EMERGENCY STOP", style: TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }
}