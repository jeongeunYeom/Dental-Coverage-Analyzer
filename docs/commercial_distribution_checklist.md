# 상용 배포 전 법률·운영 확인 목록

이 문서는 법률 자문이 아니며 출시 담당자가 전문가와 확인해야 할 항목을 기록한다.

- PyMuPDF의 현재 배포 라이선스와 상용 사용 조건을 최종 배포 방식에 맞춰 검토한다.
- PySide6/Qt의 LGPL 준수 방식 또는 별도 상용 라이선스 필요 여부를 검토한다.
- Tesseract와 tessdata의 Apache-2.0 고지 및 원문이 installer/portable 결과에 포함되는지 확인한다.
- Windows 코드 서명 인증서, timestamp 서비스와 SmartScreen reputation 계획을 검토한다.
- 개인정보 처리방침, 로컬 autosave 보관 정책과 고객용 면책문구를 검토한다.
- 포함된 모든 Python/Qt runtime dependency의 third-party notice를 출시 전에 확정한다.
