# `groundtem-io` 독립 로컬 환경 세팅 및 GitHub / PyPI 배포 가이드라인

이 문서는 `groundtem-io` 폴더를 다른 디렉토리로 복사한 뒤, **새로운 독립 로컬 프로젝트 환경**에서 바로 개발, 테스트, GitHub 업로드 및 PyPI(`pip`) 배포를 이어서 진행할 수 있도록 작성된 단계별 가이드입니다.

---

## 1. 폴더 구조 확인

복사한 `groundtem-io/` 폴더 내부는 다음과 같이 구성되어 있습니다:

```text
groundtem-io/
├── .gitignore              # Git 추적 제외 목록 (가상환경, 빌드 산출물 등)
├── LICENSE                 # MIT 오픈소스 라이선스
├── PUBLISHING_GUIDE.md     # 현재 보고 계신 배포 및 환경 설정 가이드라인
├── README.md               # GitHub 및 PyPI 메인 페이지에 표시될 영문 설명서
├── pyproject.toml          # 패키지 설정, 버전, 의존성 메타데이터
└── src/
    └── groundtem_io/
        ├── __init__.py     # 패키지 공개 API 정의
        ├── stb.py          # read_stb, read_stn, read_sounding_dir, read_survey
        ├── protocol.py     # read_protocol (.sts 프로토콜 파서)
        └── plotting.py     # plot_decay, plot_station (LM/HM 감쇠곡선 및 SNR 플롯)
```

---

## 2. 새 로컬 환경에서 프로젝트 시작하기

1. 원하는 작업 경로(예: `~/Projects/groundtem-io`)로 이 `groundtem-io` 폴더를 복사/이동합니다.
2. 터미널(또는 새로운 Antigravity/VS Code 창)에서 해당 폴더를 엽니다.
3. `pyproject.toml` 파일을 열어 수정할 항목이 있는지 확인합니다:
   - `name`: 기본값은 `"groundtem-io"`입니다. 다른 패키지명을 원하시면 `pyproject.toml`의 `name`을 변경하세요.
   - `authors`: 이름과 이메일 주소를 확인하세요.
   - `[project.urls]`: `YOUR_GITHUB_USERNAME` 부분을 본인의 GitHub 아이디로 변경하세요.

### 로컬 가상환경 생성 및 편집 모드(Editable) 설치
`uv`가 설치되어 있다면 아래 명령어로 즉시 독립 가상환경을 만들고 패키지를 테스트할 수 있습니다:

```bash
# 1. 가상환경 생성 (.venv)
uv venv

# 2. 현재 패키지를 editable 모드로 설치
uv pip install -e .

# 3. 정상 임포트 확인
uv run python -c "import groundtem_io; print(groundtem_io.__version__, groundtem_io.__all__)"
```

---

## 3. 배포 전 법적·보안 체크리스트 (필수 확인)

1. **제조사 독점 파일 포함 금지**:
   - ABEM / Guideline Geo의 공식 설치 프로그램(`.zip`, `.exe`), 내부 `.dll` 바이너리, 비공개 PDF 매뉴얼 등은 절대 이 저장소에 넣지 마세요.
2. **현장 데이터 보안 확인**:
   - 대용량 현장 로우 데이터나 대외비/미발표 연구 데이터는 커밋하지 마세요.
   - 예제 코드나 단위 테스트용 데이터가 필요하다면 공개 가능한 단일 측정점(`.stb`, `.stn` 1개 세트)만 `examples/` 또는 `tests/data/`에 최소한으로 포함하세요.
3. **비공식 오픈소스 명시**:
   - `README.md` 상단에 ABEM / Guideline Geo와 무관한 독립 오픈소스 리더임을 밝히는 Disclaimer 문구가 이미 포함되어 있습니다.

---

## 4. GitHub 저장소 생성 및 업로드

1. [GitHub](https://github.com/new)에서 `groundtem-io`라는 이름으로 새로운 **Public** 저장소를 생성합니다 (`README`, `.gitignore`, `LICENSE`는 이미 로컬에 있으므로 체크하지 않고 빈 저장소로 생성).
2. 프로젝트 폴더에서 아래 명령어를 순서대로 실행합니다:

```bash
git init
git add .
git commit -m "Initial commit: groundtem-io package for .stb, .stn, and .sts files"
git branch -M main
git remote add origin https://github.com/<본인_GitHub_아이디>/groundtem-io.git
git push -u origin main
```

---

## 5. PyPI (`pip`) 패키지 빌드 및 배포

### Step 1: PyPI 계정 및 API 토큰 준비
1. [pypi.org](https://pypi.org/)에 가입 및 로그인합니다 (2FA 이중 인증 등록 필요).
2. **Account settings** → **API tokens** → **Add API token**으로 이동합니다.
   - Token name: `groundtem-io-upload`
   - Scope: 처음 올릴 때는 `Entire account (all projects)`를 선택합니다.
3. 생성된 토큰(`pypi-AgEIcHlwaS5vcmc...`)을 안전한 곳에 복사해 둡니다.

*(연습 삼아 먼저 테스트해보고 싶다면 [test.pypi.org](https://test.pypi.org/)에서 동일하게 토큰을 발급받아 테스트할 수도 있습니다.)*

### Step 2: 패키지 빌드 (`dist/` 생성)
프로젝트 루트에서 아래 명령어를 실행합니다:

```bash
uv build
```
실행 후 `dist/` 폴더 안에 다음 두 파일이 생성되었는지 확인합니다:
- `groundtem_io-0.1.0-py3-none-any.whl`
- `groundtem_io-0.1.0.tar.gz`

### Step 3: PyPI에 업로드 (`uv publish`)
발급받은 토큰을 사용해 PyPI에 업로드합니다:

```bash
uv publish --token pypi-여기에_발급받은_토큰_입력
```

*(참고: 만약 `twine`을 선호하신다면 `uvx twine upload dist/*`로도 동일하게 업로드할 수 있습니다.)*

### Step 4: 배포 확인 및 설치 테스트
업로드가 완료되면 몇 초 내로 `https://pypi.org/project/groundtem-io/` 페이지가 활성화되며, 어디서든 아래 명령어로 설치할 수 있습니다:

```bash
pip install groundtem-io
```

---

## 6. 향후 버전 업데이트 방법

코드를 수정한 뒤 새 버전을 올리고 싶을 때는:
1. `pyproject.toml`과 `src/groundtem_io/__init__.py`의 `version`을 `"0.1.1"` 또는 `"0.2.0"`으로 올립니다.
2. 기존 빌드 파일을 지우고 다시 빌드 및 배포합니다:
   ```bash
   rm -rf dist/
   uv build
   uv publish --token pypi-여기에_발급받은_토큰_입력
   ```
