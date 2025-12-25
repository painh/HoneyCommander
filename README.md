# 꿀 커맨더 (Honey Commander)

크로스 플랫폼 파일 탐색기 + 꿀뷰 스타일 이미지 뷰어

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-Qt6-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 주요 기능

- **3단 레이아웃**: 폴더 트리 | 파일 목록 | 미리보기
- **이미지 뷰어**: 꿀뷰 스타일 전체화면 뷰어 (마우스 제스처, 확대/축소)
- **아카이브 탐색**: ZIP/RAR 파일 내부 브라우징
- **PSD 지원**: Photoshop 파일 미리보기
- **파일 작업**: 복사/붙여넣기/삭제/이름변경
- **드래그 앤 드롭**: Finder에서 파일 드래그 지원
- **실행취소/다시실행**: Cmd+Z로 삭제 복원

## 설치

### 요구사항
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 패키지 매니저

### 실행

```bash
# 저장소 클론
git clone https://github.com/painh/HoneyCommander.git
cd HoneyCommander

# 의존성 설치 및 실행
uv sync
uv run commander
```

## 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `Enter` | 파일 열기 / 폴더 이동 |
| `Space` | 전체화면 이미지 뷰어 |
| `Backspace` | 상위 폴더 |
| `Cmd+C` / `Cmd+V` | 복사 / 붙여넣기 |
| `Cmd+Z` | 실행취소 |
| `Cmd+Shift+Z` | 다시실행 |
| `Delete` | 휴지통으로 이동 |
| `F2` | 이름 변경 |

### 이미지 뷰어 (전체화면)

| 단축키 | 기능 |
|--------|------|
| `←` `→` | 이전/다음 이미지 |
| `+` `-` | 확대/축소 |
| `0` | 원본 크기 |
| `F` | 화면에 맞춤 |
| `R` | 90도 회전 |
| `Esc` | 닫기 |

## 스크린샷

<!-- TODO: 스크린샷 추가 -->

## 라이선스

MIT License - 자유롭게 사용하세요!

## 의존성 라이선스

| 라이브러리 | 라이선스 |
|-----------|---------|
| PySide6 | LGPL-3.0 |
| Pillow | HPND (MIT-like) |
| psd-tools | MIT |
| rarfile | ISC |
| send2trash | BSD-3-Clause |
