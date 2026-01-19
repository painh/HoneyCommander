# Asset Management Tools Research

게임 어셋 관리 도구 및 라이브러리 조사 결과

---

## 1. 상용/프리미엄 도구

### Eagle
> 크리에이터를 위한 디지털 어셋 관리 도구

| 항목 | 내용 |
|------|------|
| 가격 | $29.95 (1회 구매, 평생 업데이트) |
| 플랫폼 | Windows, macOS |
| 대상 | 디자이너, 아티스트 |

**핵심 기능:**
- **태깅 시스템**: 다중 태그, 자동 태깅 (폴더에 추가 시 자동 태그 부여)
- **스마트 폴더**: 조건 기반 자동 수집 (파일 타입, 날짜, 크기, 별점, 색상 등)
- **색상 필터**: 이미지 주요 색상으로 검색 (디자이너에게 유용)
- **90+ 포맷 미리보기**: 3ds, mockup, 텍스처 등
- **브라우저 확장**: 웹에서 이미지 바로 수집

**장점:**
- 직관적 UI, 빠른 검색
- 1회 구매로 구독 부담 없음
- 10GB+ 대용량 라이브러리 처리 가능

**단점:**
- 모바일 앱 없음
- 내보내기 옵션 제한적
- 버전 관리 없음

**참고할 점:**
- 폴더 + 태그 혼합 구조
- 네스티드 스마트 폴더 (스마트 폴더 안에 스마트 폴더)

> 출처: [Eagle 공식](https://en.eagle.cool/), [Eagle Blog](https://en.eagle.cool/blog/post/how-to-manage-digital-assets)

---

### Anchorpoint
> 아티스트를 위한 버전 관리 + 어셋 관리

| 항목 | 내용 |
|------|------|
| 가격 | €20/월/사용자 (인디 50% 할인), 솔로 무료 |
| 플랫폼 | Windows, macOS |
| 대상 | 게임 개발팀, 3D 아티스트 |

**핵심 기능:**
- **Git 기반**: 내부적으로 Git + LFS 사용, 하지만 UI는 단순화 (Push/Pull 버튼만)
- **파일 잠금**: 바이너리 파일 충돌 방지
- **썸네일 미리보기**: FBX, Blend, C4D 등
- **태깅 + 코멘트**: 어셋별 메타데이터 관리
- **Python 액션**: 자동화 스크립트 지원

**장점:**
- Git의 강력함 + 아티스트 친화적 UI
- Unity/Unreal 전용 설정 내장
- TB 스케일 처리 가능
- 벤더락인 없음 (메타데이터만 저장)

**단점:**
- 팀 기능은 유료
- Git 지식 있으면 오히려 답답할 수 있음

**참고할 점:**
- 버전 관리가 필요하다면 참고할 모델
- Python 액션으로 확장 가능

> 출처: [Anchorpoint 공식](https://www.anchorpoint.app), [Anchorpoint Pricing](https://www.anchorpoint.app/pricing)

---

### Mudstack
> 게임 스튜디오 전용 AI 기반 파이프라인 자동화

| 항목 | 내용 |
|------|------|
| 가격 | 문의 필요 (스튜디오 대상) |
| 플랫폼 | Web + Desktop |
| 대상 | AA급 이상 게임 스튜디오 |

**핵심 기능:**
- **버전 관리 + 어셋 관리 + 리뷰** 통합
- **AI 검색/태깅**: 자동 분류
- **세밀한 권한 관리**: 외부 벤더와 협업 시 IP 보호
- **아티스트 경험 최적화**: 크리에이티브 작업에 집중할 수 있도록

**참고할 점:**
- 엔터프라이즈급이라 개인용으로는 과함
- 하지만 기능 구성 참고 가치 있음

> 출처: [Mudstack](https://mudstack.com/)

---

### PureRef
> 레퍼런스 이미지 뷰어

| 항목 | 내용 |
|------|------|
| 가격 | 무료 (자발적 기부) |
| 플랫폼 | Windows, macOS, Linux |
| 대상 | 컨셉 아티스트, 일러스트레이터 |

**핵심 기능:**
- **자유 배치 캔버스**: 이미지를 자유롭게 배치, 회전, 크기 조절
- **무드보드 생성**: 레퍼런스 정리용
- **항상 위**: 작업 중 참고용으로 띄워두기

**장점:**
- 극도로 가벼움
- 무료

**단점:**
- **파일 관리 기능 없음** (태깅, 검색 등)
- 4년간 메이저 업데이트 없었음

**참고할 점:**
- Eagle과 함께 사용하는 경우 많음 (Eagle로 정리 → PureRef로 보기)
- 우리 도구와는 다른 영역 (뷰어 vs 관리자)

> 출처: [PureRef vs Eagle](https://syncwin.com/pureref-vs-eagle/)

---

## 2. 오픈소스 도구

### Hydrus Network
> 개인용 보루(booru) 스타일 미디어 태거

| 항목 | 내용 |
|------|------|
| 가격 | 무료 (오픈소스) |
| 플랫폼 | Windows, macOS, Linux |
| 라이선스 | WTFPL |
| 언어 | Python |

**핵심 기능:**
- **태그 기반 탐색**: 폴더 대신 태그로 모든 것을 관리
- **SHA-256 해시 기반 식별**: 파일명/경로 변경해도 추적 가능
- **태그 관계**: Sibling (별칭), Parent (상위 태그 자동 부여)
- **태그 서비스 분리**: 여러 태그 DB 운영 가능
- **공개 태그 저장소**: 10억+ 태그 공유 (선택적 참여)
- **웹사이트 다운로더**: 부루/갤러리 사이트에서 태그와 함께 다운로드

**장점:**
- 완전 로컬, 프라이버시 중심
- 해시 기반이라 파일 이동해도 태그 유지
- 강력한 태그 시스템 (보루 스타일)

**단점:**
- UI가 복잡함 (러닝커브 높음)
- 일반 파일 탐색기와 병행 어려움

**참고할 점:**
- **해시 기반 파일 식별** 우리 아이디어와 동일
- **태그 Sibling/Parent 시스템** 참고할 만함

> 출처: [Hydrus GitHub](https://github.com/hydrusnetwork/hydrus), [Hydrus Docs](https://hydrusnetwork.github.io/hydrus/introduction.html)

---

### digiKam
> 오픈소스 사진 관리 애플리케이션

| 항목 | 내용 |
|------|------|
| 가격 | 무료 (오픈소스) |
| 플랫폼 | Windows, macOS, Linux |
| 라이선스 | GPL |
| 언어 | C++ (KDE) |

**핵심 기능:**
- **태그 + 라벨 + 별점**: 다차원 분류
- **얼굴 인식**: AI 기반 인물 태깅
- **AI 자동 태깅**: 장면, 객체, 동물, 분위기 자동 인식
- **메타데이터**: EXIF, IPTC, XMP 완벽 지원
- **Sidecar 파일**: XMP 메타데이터 별도 저장 가능
- **200+ RAW 포맷** 지원

**장점:**
- 완전 로컬 (클라우드 없음)
- AI가 로컬에서 동작 (프라이버시)
- 성숙한 프로젝트

**단점:**
- 사진 전용 (게임 어셋에는 과함)
- KDE 기반이라 무거움

**참고할 점:**
- **XMP Sidecar** 방식 참고
- **AI 태깅**을 로컬에서 하는 방법

> 출처: [digiKam 공식](https://www.digikam.org/), [digiKam Features](https://www.digikam.org/about/features/)

---

### ResourceSpace
> 웹 기반 오픈소스 DAM

| 항목 | 내용 |
|------|------|
| 가격 | 무료 (오픈소스), 호스팅 버전 유료 |
| 플랫폼 | 웹 (PHP) |
| 라이선스 | BSD |

**핵심 기능:**
- **메타데이터 도구**: 강력한 메타데이터 관리
- **버전 관리**: 파일 버전 추적
- **자동 태깅 + AI 검색**
- **팀 협업**: 웹 기반이라 공유 쉬움

**참고할 점:**
- 웹 기반이라 우리 케이스와는 다름
- 하지만 메타데이터 스키마 참고 가능

> 출처: [ResourceSpace](https://www.resourcespace.com/)

---

## 3. Python 라이브러리

### OpenAssetIO
> 미디어 프로덕션용 자산 관리 표준

| 항목 | 내용 |
|------|------|
| 언어 | C++ + Python 바인딩 |
| 라이선스 | Apache 2.0 |
| 관리 | ASWF (Academy Software Foundation) |

**핵심 기능:**
- **경로 대신 ID로 참조**: 파일 이동해도 추적 가능
- **메타데이터 전달**: 어셋 관리 시스템에서 파라미터 전달
- **파이프라인 통합**: Maya, Nuke 등과 연동

**참고할 점:**
- VFX 파이프라인용이라 우리에겐 과함
- 하지만 "경로 대신 ID" 개념은 우리 아이디어와 동일

> 출처: [OpenAssetIO GitHub](https://github.com/OpenAssetIO/OpenAssetIO)

---

### MADAM (Multimedia Advanced Digital Asset Management)
> Python용 미디어 어셋 처리 라이브러리

| 항목 | 내용 |
|------|------|
| 언어 | Python |
| 라이선스 | AGPLv3 |
| PyPI | `pip install MADAM` |

**핵심 기능:**
- 이미지/오디오/비디오 파일 핸들링
- 저장, 정리, 변환 지원

**참고할 점:**
- 가벼운 라이브러리
- 하지만 태깅/DB 기능은 없음

> 출처: [MADAM PyPI](https://pypi.org/project/MADAM/), [MADAM GitHub](https://github.com/eseifert/madam)

---

## 4. 기능별 비교표

| 기능 | Eagle | Anchorpoint | Hydrus | digiKam | PureRef |
|------|:-----:|:-----------:|:------:|:-------:|:-------:|
| 태그 시스템 | ★★★ | ★★ | ★★★★ | ★★★ | ✗ |
| 스마트 폴더 | ★★★ | ✗ | ★★★ | ★★ | ✗ |
| 색상 검색 | ★★★ | ✗ | ✗ | ✗ | ✗ |
| 버전 관리 | ✗ | ★★★★ | ✗ | ✗ | ✗ |
| 해시 기반 ID | ✗ | ✗ | ★★★★ | ✗ | ✗ |
| 메타데이터 | ★★ | ★★ | ★★ | ★★★★ | ✗ |
| AI 태깅 | ✗ | ✗ | ✗ | ★★★ | ✗ |
| 오픈소스 | ✗ | ✗ | ★★★★ | ★★★★ | ✗ |
| 게임 어셋 특화 | ✗ | ★★★ | ✗ | ✗ | ✗ |

---

## 5. Commander 어셋 관리자에 적용할 인사이트

### 파일 식별 (Hydrus 참고)
```
- SHA-256 해시 기반 (Hydrus 방식)
- 우리는 Partial Hash로 최적화
- 파일 이동/이름 변경해도 추적 가능
```

### 태그 시스템 (Eagle + Hydrus 참고)
```
- 다중 태그 지원
- 태그 별칭 (Sibling): "char" = "character"
- 태그 상속 (Parent): "boss" 태그 → 자동으로 "enemy" 태그도
- 네임스페이스: "character:player", "type:sprite"
- 자동 태깅: 폴더에 넣으면 자동 태그 부여
```

### 스마트 컬렉션 (Eagle 참고)
```
- 조건 기반 자동 수집
- 네스티드 스마트 폴더
- 조건: 태그, 파일타입, 크기, 날짜, 별점, 색상
```

### 메타데이터 저장 (digiKam 참고)
```
- SQLite (빠른 검색)
- 선택적 XMP Sidecar 내보내기 (이식성)
```

### UI 구조 (Eagle 참고)
```
- 라이브러리(루트 폴더) 개념
- 폴더 구조 + 태그 필터 병행
- 속성 패널 (우측 사이드바)
- 색상 필터 (선택적)
```

---

## 6. 참고 링크 모음

**상용:**
- [Eagle 공식](https://en.eagle.cool/)
- [Anchorpoint 공식](https://www.anchorpoint.app)
- [Mudstack](https://mudstack.com/)
- [PureRef](https://www.pureref.com/)

**오픈소스:**
- [Hydrus Network GitHub](https://github.com/hydrusnetwork/hydrus)
- [digiKam 공식](https://www.digikam.org/)
- [ResourceSpace](https://www.resourcespace.com/)
- [OpenAssetIO GitHub](https://github.com/OpenAssetIO/OpenAssetIO)

**리서치:**
- [3D Asset Management 비교 (echo3D)](https://medium.com/echo3d/a-comparison-of-3d-asset-management-software-for-game-art-fc17e0f36fd9)
- [DAM for Game Developers](https://picajet.com/articles/digital-asset-management-for-game-developers/)
- [오픈소스 DAM 5선 (XDA)](https://www.xda-developers.com/best-open-source-digital-asset-management-tools/)
