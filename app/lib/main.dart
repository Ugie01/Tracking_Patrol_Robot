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
          background: const Color(0xFFF5F7F8),
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
  // 블루투스 상태 변수
  List<BluetoothDevice> _devicesList = [];
  BluetoothDevice? _selectedDevice;
  BluetoothConnection? _connection;
  bool _isConnecting = false;
  bool _isScanning = false;
  StreamSubscription<BluetoothDiscoveryResult>? _discoveryStreamSubscription;
  bool get _isConnected => (_connection?.isConnected ?? false);

  // 제어 상태 변수
  int _leftPwm = 0;
  int _rightPwm = 0;
  DateTime? _lastSendTime;
  final int _throttleMs = 50;

  // UI 모드 (0: 슬라이더, 1: 버튼, 2: 트래킹)
  int _controlMode = 0;

  // 트래킹 모드 상태 (0: 정지, 1: 활성)
  int _trackingState = 0;

  @override
  void initState() {
    super.initState();
    _initBluetooth();
  }

  Future<void> _initBluetooth() async {
    await [
      Permission.bluetooth,
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.location,
    ].request();
    _loadBondedDevices();
  }

  // 페어링된 기기 불러오기
  Future<void> _loadBondedDevices() async {
    try {
      List<BluetoothDevice> bondedDevices = await FlutterBluetoothSerial.instance.getBondedDevices();
      setState(() {
        // 기존 검색된 목록과 병합하되, 중복 제거
        for (var device in bondedDevices) {
          if (!_devicesList.any((d) => d.address == device.address)) {
            _devicesList.add(device);
          }
        }
        if (_selectedDevice == null && _devicesList.isNotEmpty) {
          _selectedDevice = _devicesList.firstWhere(
                (d) => d.name?.contains("HC") ?? false,
            orElse: () => _devicesList.first,
          );
        }
      });
    } catch (e) {
      debugPrint("기기 목록 로드 오류: $e");
    }
  }

  // 주변 블루투스 기기 실시간 스캔 (재검색)
  void _startDiscovery() {
    if (_isScanning) return;

    setState(() {
      _isScanning = true;
      // 스캔 시 기존 연결되지 않은 기기 목록 초기화 (페어링된 기기는 유지)
      _devicesList.removeWhere((d) => !d.isBonded);
    });

    _loadBondedDevices(); // 페어링된 기기 베이스라인 구성

    _discoveryStreamSubscription = FlutterBluetoothSerial.instance.startDiscovery().listen((r) {
      setState(() {
        if (!_devicesList.any((d) => d.address == r.device.address)) {
          _devicesList.add(r.device);
        }
      });
    });

    _discoveryStreamSubscription?.onDone(() {
      if (mounted) setState(() => _isScanning = false);
    });

    // 5초 후 스캔 자동 종료 방어 로직
    Future.delayed(const Duration(seconds: 5), () {
      if (_isScanning) {
        _discoveryStreamSubscription?.cancel();
        if (mounted) setState(() => _isScanning = false);
      }
    });
  }

  // 연결 / 해제 토글
  Future<void> _toggleConnection() async {
    if (_isConnected) {
      await _connection?.close();
      setState(() => _connection = null);
      return;
    }
    if (_selectedDevice == null) return;

    setState(() => _isConnecting = true);
    // 스캔 중이라면 중지
    if (_isScanning) {
      _discoveryStreamSubscription?.cancel();
      _isScanning = false;
    }

    try {
      _connection = await BluetoothConnection.toAddress(_selectedDevice!.address);
      _connection!.input!.listen((data) {}).onDone(() {
        if (mounted) setState(() => _connection = null);
      });
      // 연결 성공 시 초기 정지 명령 전송
      _sendControlData(0, 0);
    } catch (e) {
      debugPrint('연결 실패: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('연결 실패. 기기 전원을 확인하세요.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isConnecting = false);
    }
  }

  // 확장된 7-Byte 프로토콜 전송 함수
  void _sendControlData(int leftSpeed, int rightSpeed) {
    // if (!_isConnected) return;

    // 스로틀링 (트래킹 모드가 아닐 때만 적용, 트래킹 모드 전환 명령은 즉각 전송)
    if (_controlMode != 2) {
      final now = DateTime.now();
      if (_lastSendTime != null && now.difference(_lastSendTime!).inMilliseconds < _throttleMs) return;
      _lastSendTime = now;
    }

    // 모드 플래그: 트래킹 모드면 1, 수동 모드(슬라이더/버튼)면 0
    int modeFlag = (_controlMode == 2 && _trackingState == 1) ? 1 : 0;

    int lDir = leftSpeed >= 0 ? 0 : 1;
    int rDir = rightSpeed >= 0 ? 0 : 1;
    int lPwm = leftSpeed.abs().clamp(0, 255);
    int rPwm = rightSpeed.abs().clamp(0, 255);

    // 변경된 7바이트 규격: [시작(0xAA), 모드, 좌방향, 좌PWM, 우방향, 우PWM, 종료(0x55)]
    Uint8List packet = Uint8List.fromList([0xAA, modeFlag, lDir, lPwm, rDir, rPwm, 0x55]);

    String hexPacket = packet.map((b) => '0x${b.toRadixString(16).padLeft(2, '0').toUpperCase()}').join(', ');

    // 모드에 따라 태그를 달아서 출력
    String modeName = _controlMode == 0 ? "슬라이더" : (_controlMode == 1 ? "버튼" : "트래킹");
    debugPrint("[$modeName 모드] 생성된 패킷: [$hexPacket]");

    try {
      _connection!.output.add(packet);
      _connection!.output.allSent;
      debugPrint("전송 패킷: $packet"); // 디버깅용 출력
    } catch (e) {
      debugPrint("전송 오류: $e");
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
      backgroundColor: colorScheme.background,
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 12, height: 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isConnected ? Colors.green : Colors.red,
                boxShadow: [BoxShadow(color: _isConnected ? Colors.green.withOpacity(0.5) : Colors.red.withOpacity(0.5), blurRadius: 4)],
              ),
            ),
            const SizedBox(width: 10),
            const Text('Tracking Robot Controller', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
          ],
        ),
        backgroundColor: Colors.white,
        elevation: 0,
      ),
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16.0),
        child: Column(
          children: [
            const SizedBox(height: 10),
            _buildConnectionCard(colorScheme),
            const SizedBox(height: 20),
            _buildModeToggle(colorScheme),
            Expanded(
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 20),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.5),
                  borderRadius: BorderRadius.circular(24),
                ),
                child: _buildCurrentModeUI(),
              ),
            ),
            _buildEmergencyStop(),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  // 1. 블루투스 연결 카드 (재검색 버튼 포함)
  Widget _buildConnectionCard(ColorScheme colorScheme) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Row(
          children: [
            Expanded(
              child: DropdownButtonHideUnderline(
                child: DropdownButton<BluetoothDevice>(
                  isExpanded: true,
                  value: _selectedDevice,
                  hint: const Text("장치를 선택하세요"),
                  items: _devicesList.map((d) {
                    return DropdownMenuItem(
                      value: d,
                      child: Text(
                        d.name == null || d.name!.isEmpty ? d.address : "${d.name} ${d.isBonded ? '(페어링됨)' : ''}",
                        overflow: TextOverflow.ellipsis,
                      ),
                    );
                  }).toList(),
                  onChanged: _isConnected ? null : (val) => setState(() => _selectedDevice = val),
                ),
              ),
            ),
            // 재검색(스캔) 버튼
            IconButton(
              icon: _isScanning
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.search, color: Colors.blueGrey),
              onPressed: (_isConnected || _isScanning) ? null : _startDiscovery,
              tooltip: '기기 재검색',
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: _isConnecting ? null : _toggleConnection,
              style: ElevatedButton.styleFrom(
                backgroundColor: _isConnected ? colorScheme.errorContainer : colorScheme.primaryContainer,
                foregroundColor: _isConnected ? colorScheme.error : colorScheme.primary,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: _isConnecting
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(_isConnected ? '연결 해제' : '연결'),
            ),
          ],
        ),
      ),
    );
  }

  // 2. 모드 전환 토글 (트래킹 추가됨)
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
          _leftPwm = 0;
          _rightPwm = 0;
          _trackingState = 0; // 모드 변경 시 트래킹 정지 상태로 초기화
        });
        _sendControlData(0, 0); // 상태 변경 시 안전을 위한 정지 패킷 전송
      },
      style: SegmentedButton.styleFrom(
        side: BorderSide(color: colorScheme.outlineVariant),
        backgroundColor: Colors.white,
        selectedBackgroundColor: colorScheme.primaryContainer,
      ),
    );
  }

  // 선택된 모드에 따라 UI 렌더링
  Widget _buildCurrentModeUI() {
    if (_controlMode == 0) return _buildSliderUI();
    if (_controlMode == 1) return _buildButtonUI();
    return _buildTrackingUI(); // 트래킹 모드
  }

  // 3-1. 슬라이더 UI
  Widget _buildSliderUI() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        _buildSingleVerticalSlider("LEFT", _leftPwm, (val) {
          setState(() => _leftPwm = val.toInt());
          _sendControlData(_leftPwm, _rightPwm);
        }),
        _buildSingleVerticalSlider("RIGHT", _rightPwm, (val) {
          setState(() => _rightPwm = val.toInt());
          _sendControlData(_leftPwm, _rightPwm);
        }),
      ],
    );
  }

  Widget _buildSingleVerticalSlider(String label, int value, ValueChanged<double> onChanged) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
        const SizedBox(height: 10),
        Container(
          height: 250,
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(color: Colors.grey.shade100, borderRadius: BorderRadius.circular(30)),
          child: RotatedBox(
            quarterTurns: 3,
            child: Slider(
              value: value.toDouble(), min: -255, max: 255,
              onChanged: onChanged,
              onChangeEnd: (_) => onChanged(0),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text("$value", style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
      ],
    );
  }

  // 3-2. 버튼 UI
  Widget _buildButtonUI() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _buildDirectionButton(Icons.keyboard_arrow_up, 255, 255),
        const SizedBox(height: 20),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildDirectionButton(Icons.keyboard_arrow_left, -200, 200),
            const SizedBox(width: 80),
            _buildDirectionButton(Icons.keyboard_arrow_right, 200, -200),
          ],
        ),
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
      child: Container(
        width: 75, height: 75,
        decoration: BoxDecoration(
          color: Colors.white, shape: BoxShape.circle,
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 10, offset: const Offset(0, 5))],
        ),
        child: Icon(icon, size: 40, color: Colors.blueGrey),
      ),
    );
  }

  // 3-3. 트래킹 모드 전용 UI
  Widget _buildTrackingUI() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.visibility, size: 60, color: Colors.blueGrey),
        const SizedBox(height: 20),
        const Text("자율 트래킹 시스템 가동 대기 중", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.blueGrey)),
        const SizedBox(height: 40),
        // 트래킹 시작/정지 토글 버튼 (PWM은 0으로 고정하여 전송)
        ElevatedButton.icon(
          onPressed: () {
            setState(() => _trackingState = _trackingState == 0 ? 1 : 0);
            // 트래킹 모드 상태를 STM32에 알림 (모드값 1, PWM은 0)
            _sendControlData(0, 0);
          },
          icon: Icon(_trackingState == 0 ? Icons.play_arrow : Icons.pause, size: 30),
          label: Text(_trackingState == 0 ? "트래킹 시작" : "트래킹 일시정지", style: const TextStyle(fontSize: 18)),
          style: ElevatedButton.styleFrom(
            backgroundColor: _trackingState == 0 ? Colors.blue.shade100 : Colors.orange.shade100,
            foregroundColor: _trackingState == 0 ? Colors.blue.shade800 : Colors.orange.shade800,
            padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 15),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          ),
        ),
        const SizedBox(height: 20),
        if (_trackingState == 1)
          const Text("STM32 알고리즘에 의해 자동 제어 중입니다.", style: TextStyle(color: Colors.orange, fontWeight: FontWeight.w500)),
      ],
    );
  }

  // 4. 긴급 정지 (어떤 모드에서든 수동 정지 패킷(모드0, PWM0) 전송)
  Widget _buildEmergencyStop() {
    return SizedBox(
      width: double.infinity, height: 60,
      child: ElevatedButton(
        onPressed: () {
          setState(() {
            _leftPwm = 0;
            _rightPwm = 0;
            _controlMode = 0; // 슬라이더 모드로 강제 복귀
            _trackingState = 0;
          });
          _sendControlData(0, 0); // 강제 모드 0(수동) 및 정지 명령 하달
        },
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFFFFE5E5),
          foregroundColor: Colors.red,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
        child: const Text("EMERGENCY STOP & RESET", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
      ),
    );
  }
}