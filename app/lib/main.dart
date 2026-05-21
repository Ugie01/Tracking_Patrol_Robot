import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_bluetooth_serial/flutter_bluetooth_serial.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

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

  final List<int> _rxBuffer = [];

  @override
  void initState() {
    super.initState();
    _initBluetooth();
    _loadDefaultPidValues();
  }

  Future<void> _initBluetooth() async {
    await [Permission.bluetooth, Permission.bluetoothScan, Permission.bluetoothConnect, Permission.location].request();
    _loadBondedDevices();
  }

  Future<void> _loadDefaultPidValues() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _pVal = prefs.getDouble('default_p') ?? 0;
      _iVal = prefs.getDouble('default_i') ?? 0;
      _dVal = prefs.getDouble('default_d') ?? 0;
    });
  }

  Future<void> _savePidPreset(int slot) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('slot_${slot}_p', _pVal);
    await prefs.setDouble('slot_${slot}_i', _iVal);
    await prefs.setDouble('slot_${slot}_d', _dVal);
    await prefs.setDouble('default_p', _pVal);
    await prefs.setDouble('default_i', _iVal);
    await prefs.setDouble('default_d', _dVal);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('슬롯 $slot에 PID 파라미터가 저장되었습니다! (P:${_pVal.toInt()}, I:${_iVal.toInt()}, D:${_dVal.toInt()})')),
      );
    }
  }

  Future<void> _loadPidPreset(int slot) async {
    final prefs = await SharedPreferences.getInstance();
    double? p = prefs.getDouble('slot_${slot}_p');
    double? i = prefs.getDouble('slot_${slot}_i');
    double? d = prefs.getDouble('slot_${slot}_d');

    if (p == null || i == null || d == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('슬롯 $slot에 저장된 데이터가 없습니다.')));
      }
      return;
    }
    setState(() { _pVal = p; _iVal = i; _dVal = d; });
    _sendControlData(_leftPwm, _rightPwm);
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
      _connection!.input!.listen(_onDataReceived).onDone(() {
        if (mounted) setState(() => _connection = null);
      });
      _sendControlData(0, 0);
    } catch (e) { debugPrint('연결 실패: $e'); }
    finally { if (mounted) setState(() => _isConnecting = false); }
  }

  void _onDataReceived(Uint8List data) {
    _rxBuffer.addAll(data);
    while (_rxBuffer.length >= 12) {
      if (_rxBuffer[0] == 0xAA && _rxBuffer[11] == 0x55) {
        _rxBuffer.removeRange(0, 12);
      } else {
        _rxBuffer.removeAt(0);
      }
    }
  }

  // 16진수 실시간 터미널 출력 로직이 결합된 데이터 송신부
  void _sendControlData(int leftSpeed, int rightSpeed) {
    bool isStopCommand = (leftSpeed == 0 && rightSpeed == 0);

    // 수동모드 주행 제어 시에만 50ms 스로틀링 제한 적용 (정지 패킷은 즉시 전송 예외처리)
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

    // [0xAA, 모드, L_방향, L_PWM, R_방향, R_PWM, P, I, D, 0x55] -> 10바이트 데이터 프레임 팩트 데이터 빌드
    Uint8List packet = Uint8List.fromList([
      0xAA, modeFlag, lDir, lPwm, rDir, rPwm,
      _pVal.toInt(), _iVal.toInt(), _dVal.toInt(), 0x55
    ]);

    // -------------------------------------------------------------------------
    // [실시간 터미널 출력 디버깅 영역] 블루투스가 끊겨있어도 패킷 분석이 가능하도록 상단 배치
    String hexString = packet.map((b) => '0x${b.toRadixString(16).padLeft(2, '0').toUpperCase()}').join(', ');
    String modeName = _controlMode == 0 ? "Slider" : (_controlMode == 1 ? "Button" : "Tracking");
    debugPrint("[$modeName 모드 전송 로그] [$hexString]");
    // -------------------------------------------------------------------------

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
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Row(
            children: [
              Container(width: 12, height: 12, decoration: BoxDecoration(shape: BoxShape.circle, color: _isConnected ? Colors.green : Colors.red)),
              const SizedBox(width: 10),
              const Text('Robot System Controller'),
            ],
          ),
          bottom: const TabBar(
            labelStyle: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            tabs: [
              Tab(icon: Icon(Icons.directions_run), text: '주행 메인'),
              Tab(icon: Icon(Icons.tune), text: 'PID 튜닝'),
            ],
          ),
        ),
        body: TabBarView(
          physics: const NeverScrollableScrollPhysics(),
          children: [
            _buildDriveTab(colorScheme),
            _buildPidTab(colorScheme),
          ],
        ),
      ),
    );
  }

  Widget _buildDriveTab(ColorScheme colorScheme) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            _buildConnectionCard(colorScheme),
            const SizedBox(height: 15),
            _buildModeToggle(colorScheme),
            const SizedBox(height: 10),
            Container(height: 400, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24)), child: _buildCurrentModeUI()),
            const SizedBox(height: 20),
            _buildEmergencyStop(),
          ],
        ),
      ),
    );
  }

  Widget _buildPidTab(ColorScheme colorScheme) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Card(
              elevation: 0,
              color: colorScheme.secondaryContainer.withOpacity(0.25),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.tune, color: Colors.blueGrey),
                        SizedBox(width: 8),
                        Text("PID Raw Parameters (0 ~ 100)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      ],
                    ),
                    const SizedBox(height: 24),
                    _buildHorizontalPidSlider("P Gain", _pVal, (v) => setState(() => _pVal = v)),
                    const SizedBox(height: 20),
                    _buildHorizontalPidSlider("I Gain", _iVal, (v) => setState(() => _iVal = v)),
                    const SizedBox(height: 20),
                    _buildHorizontalPidSlider("D Gain", _dVal, (v) => setState(() => _dVal = v)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 15),
            Card(
              elevation: 0,
              color: Colors.white,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text("환경별 프리셋 저장소", style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 16),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [1, 2, 3].map((slot) {
                        return Container(
                          width: 95,
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(color: Colors.grey.shade50, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.grey.shade200)),
                          child: Column(
                            children: [
                              Text('슬롯 $slot', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                              const SizedBox(height: 8),
                              ElevatedButton(
                                style: ElevatedButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(75, 30)),
                                onPressed: () => _loadPidPreset(slot),
                                child: const Text('로드', style: TextStyle(fontSize: 11)),
                              ),
                              const SizedBox(height: 4),
                              IconButton(
                                icon: const Icon(Icons.save_as, size: 20),
                                onPressed: () => _savePidPreset(slot),
                              )
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHorizontalPidSlider(String label, double value, ValueChanged<double> onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)),
              child: Text("${value.toInt()}", style: const TextStyle(fontFamily: 'Courier', fontWeight: FontWeight.bold, fontSize: 16, color: Colors.indigo)),
            ),
          ],
        ),
        Row(
          children: [
            IconButton(
              icon: const Icon(Icons.remove_circle_outline, color: Colors.redAccent),
              onPressed: value > 0 ? () { onChanged(value - 1); _sendControlData(_leftPwm, _rightPwm); } : null,
            ),
            Expanded(
              child: Slider(
                  value: value, min: 0, max: 100, divisions: 100,
                  onChanged: (v) { onChanged(v); _sendControlData(_leftPwm, _rightPwm); }
              ),
            ),
            IconButton(
              icon: const Icon(Icons.add_circle_outline, color: Colors.green),
              onPressed: value < 100 ? () { onChanged(value + 1); _sendControlData(_leftPwm, _rightPwm); } : null,
            ),
          ],
        ),
      ],
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
      onTapUp: (_) => _sendControlData(0, 0),
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