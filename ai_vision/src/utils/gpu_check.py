# ----------------------------------------
# GPU 환경 자동 최적화 모듈 : 학습 전 메모리 캐시를 비우고 학습에 적합한 장치(Device)를 반환
#  -> GPU 상태 점검 및 최적화된 디바이스 객체 반환
#  -> CUDA 가용성 확인, GPU 상세 정보 출력, 메모리 정리, 고정 연산 최적화
# ----------------------------------------



import torch
import os



def get_validated_device():
    """
    GPU 상태를 점검하고 최적화된 디바이스 객체를 반환합니다.
    """
    print("\n" + "="*50)
    print("🔍 [GPU 시스템 점검 시작]")
    
    # 1. CUDA 가용성 확인
    cuda_available = torch.cuda.is_available()
    
    if not cuda_available:
        print("❌ 에러: NVIDIA GPU(CUDA)가 감지되지 않습니다.")
        print("   - 해결책 1: NVIDIA 드라이버가 설치되어 있는지 확인하세요.")
        print("   - 해결책 2: 가상환경에 'torch-gpu' 버전이 설치되었는지 확인하세요.")
        print("   - 현재 상태에서 학습 진행 시 시스템 부하로 PC가 정지될 수 있습니다.")
        return None

    # 2. GPU 상세 정보 출력
    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    
    print(f"✅ GPU 감지 성공: {device_name}")
    print(f"✅ 사용 가능 GPU 개수: {device_count}")
    
    # 3. GPU 메모리 정리 (혹시 모를 잔여 데이터 비우기)
    torch.cuda.empty_cache()
    
    # 4. 고정 연산 최적화 (학습 속도 향상)
    torch.backends.cudnn.benchmark = True
    
    print("🚀 GPU 환경 최적화 완료. 학습을 시작할 준비가 되었습니다.")
    print("="*50 + "\n")
    
    return 0  # GPU 0번 인덱스 반환



if __name__ == "__main__":
    # 단독 실행 시 테스트용
    get_validated_device()