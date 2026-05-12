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

  double _pVal = 0;
  double _iVal = 0;
  double _dVal = 0;
  double _buttonBaseSpeed = 200;

  int _controlMode = 0; // 0: Slider, 1: Button, 2: Tracking
  int _trackingState = 0;

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

  // 수정된 10-Byte 전송 함수 (스로틀링 예외처리 적용)
  void _sendControlData(int leftSpeed, int rightSpeed) {
    bool isStopCommand = (leftSpeed == 0 && rightSpeed == 0);

    // 수동 모드이면서 정지 명령이 아닐 때만 50ms 제한 적용
    if (_controlMode != 2 && !isStopCommand) {
      final now = DateTime.now();
      if (_lastSendTime != null && now.difference(_lastSendTime!).inMilliseconds < _throttleMs) return;
      _lastSendTime = now;
    }

    int modeFlag = (_controlMode == 2 && _trackingState == 1) ? 1 : 0;
    int lDir = leftSpeed >= 0 ? 0 : 1;
    int rDir = rightSpeed >= 0 ? 0 : 1;
    int lPwm = leftSpeed.abs().clamp(0, 255);
    int rPwm = rightSpeed.abs().clamp(0, 255);

    Uint8List packet = Uint8List.fromList([
      0xAA, modeFlag, lDir, lPwm, rDir, rPwm,
      _pVal.toInt(), _iVal.toInt(), _dVal.toInt(), 0x55
    ]);

    // 디버깅 콘솔 출력
    String hexString = packet.map((b) => '0x${b.toRadixString(16).padLeft(2, '0').toUpperCase()}').join(', ');
    debugPrint("[Mode: $_controlMode] Out: $hexString");

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
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              _buildConnectionCard(colorScheme),
              const SizedBox(height: 10),
              _buildPidSettingsCard(colorScheme),
              const SizedBox(height: 10),
              _buildModeToggle(colorScheme),
              const SizedBox(height: 10),
              Container(
                height: 420,
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24)),
                child: _buildCurrentModeUI(),
              ),
              const SizedBox(height: 20),
              _buildEmergencyStop(),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildConnectionCard(ColorScheme colorScheme) {
    return Card(
      elevation: 0, color: Colors.white,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 4.0),
        child: Row(
          children: [
            Expanded(child: DropdownButtonHideUnderline(child: DropdownButton<BluetoothDevice>(isExpanded: true, value: _selectedDevice, items: _devicesList.map((d) => DropdownMenuItem(value: d, child: Text(d.name ?? d.address, overflow: TextOverflow.ellipsis))).toList(), onChanged: _isConnected ? null : (val) => setState(() => _selectedDevice = val)))),
            IconButton(icon: Icon(_isScanning ? Icons.sync : Icons.search), onPressed: (_isConnected || _isScanning) ? null : _startDiscovery),
            ElevatedButton(onPressed: _isConnecting ? null : _toggleConnection, child: Text(_isConnected ? '해제' : '연결')),
          ],
        ),
      ),
    );
  }

  Widget _buildPidSettingsCard(ColorScheme colorScheme) {
    return Card(
      elevation: 0, color: colorScheme.secondaryContainer.withOpacity(0.3),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          children: [
            const Text("PID Control Parameters", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 8),
            Row(
              children: [
                _buildPidSlider("P", _pVal, (v) => setState(() => _pVal = v)),
                _buildPidSlider("I", _iVal, (v) => setState(() => _iVal = v)),
                _buildPidSlider("D", _dVal, (v) => setState(() => _dVal = v)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPidSlider(String label, double value, ValueChanged<double> onChanged) {
    return Expanded(
      child: Column(
        children: [
          Text("$label: ${value.toInt()}"),
          Slider(value: value, min: 0, max: 100, divisions: 100, onChanged: (v) { onChanged(v); _sendControlData(_leftPwm, _rightPwm); }),
        ],
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
        setState(() { _controlMode = val.first; _leftPwm = 0; _rightPwm = 0; _trackingState = 0; });
        _sendControlData(0, 0);
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
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 10),
        Container(
          height: 250, decoration: BoxDecoration(color: Colors.grey.shade100, borderRadius: BorderRadius.circular(30)),
          child: RotatedBox(quarterTurns: 3, child: Slider(value: value.toDouble(), min: -255, max: 255, onChanged: onChanged)),
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
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.speed, size: 18),
            const SizedBox(width: 10),
            SizedBox(
              width: 200,
              child: Slider(
                value: _buttonBaseSpeed, min: 0, max: 255, divisions: 255,
                onChanged: (v) => setState(() => _buttonBaseSpeed = v),
              ),
            ),
            Text("${_buttonBaseSpeed.toInt()}"),
          ],
        ),
        const SizedBox(height: 20),
        _buildDirectionButton(Icons.keyboard_arrow_up, _buttonBaseSpeed.toInt(), _buttonBaseSpeed.toInt()),
        const SizedBox(height: 15),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildDirectionButton(Icons.keyboard_arrow_left, -(_buttonBaseSpeed ~/ 1.5).toInt(), (_buttonBaseSpeed ~/ 1.5).toInt()),
            const SizedBox(width: 50),
            _buildDirectionButton(Icons.keyboard_arrow_right, (_buttonBaseSpeed ~/ 1.5).toInt(), -(_buttonBaseSpeed ~/ 1.5).toInt()),
          ],
        ),
        const SizedBox(height: 15),
        _buildDirectionButton(Icons.keyboard_arrow_down, -_buttonBaseSpeed.toInt(), -_buttonBaseSpeed.toInt()),
      ],
    );
  }

  Widget _buildDirectionButton(IconData icon, int l, int r) {
    return GestureDetector(
      onTapDown: (_) => _sendControlData(l, r),
      onTapUp: (_) => _sendControlData(0, 0), // 팩트체크: 수정된 로직에 의해 즉시 0 전송
      onTapCancel: () => _sendControlData(0, 0),
      child: Container(
          width: 85, height: 85,
          decoration: BoxDecoration(color: Colors.grey.shade100, shape: BoxShape.circle, boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 10)]),
          child: Icon(icon, size: 50, color: Colors.blueGrey)
      ),
    );
  }

  Widget _buildTrackingUI() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.visibility, size: 60, color: Colors.blueGrey),
        const SizedBox(height: 40),
        ElevatedButton.icon(
          onPressed: () { setState(() => _trackingState = _trackingState == 0 ? 1 : 0); _sendControlData(0, 0); },
          icon: Icon(_trackingState == 0 ? Icons.play_arrow : Icons.pause),
          label: Text(_trackingState == 0 ? "트래킹 시작" : "트래킹 일시정지"),
          style: ElevatedButton.styleFrom(minimumSize: const Size(220, 65)),
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
        child: const Text("EMERGENCY STOP", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
      ),
    );
  }
}