"""Korean corpus activation clauses and retained topic/method boundaries.

The twelve genuine missing-trigger descriptions keep their H1.8 findings.
The generic purpose marker 위한 also occurs in the topic-only Korean FP's
feature announcement, so mapping that marker would erase genuine findings.
"""

import pytest

from lintlang.detectors.h1 import _SKILL_TRIGGER, _detect_skill_metadata
from lintlang.detectors.lang import detect, normalize
from lintlang.models import AgentConfig, SkillMeta


@pytest.mark.parametrize("description", [
    "Node.js, Express, Next.js API 라우트를 위한 백엔드 아키텍처 패턴, API 설계, 데이터베이스 최적화 및 서버 사이드 모범 사례.",
    "TypeScript, JavaScript, React, Node.js 개발을 위한 범용 코딩 표준, 모범 사례 및 패턴.",
    "React, Next.js, 상태 관리, 성능 최적화 및 UI 모범 사례를 위한 프론트엔드 개발 패턴.",
    "견고하고 효율적이며 유지보수 가능한 Go 애플리케이션 구축을 위한 관용적 Go 패턴, 모범 사례 및 규칙.",
    "테이블 주도 테스트, 서브테스트, 벤치마크, 퍼징, 테스트 커버리지를 포함한 Go 테스팅 패턴. 관용적 Go 관행과 함께 TDD 방법론을 따릅니다.",
    "서브에이전트 컨텍스트 문제를 해결하기 위한 점진적 컨텍스트 검색 개선 패턴",
    "쿼리 최적화, 스키마 설계, 인덱싱, 보안을 위한 PostgreSQL 데이터베이스 패턴. Supabase 모범 사례 기반.",
    # Additional labeled TPs outside the original KEEP-only cohort.
    "고성능 분석 워크로드를 위한 ClickHouse 데이터베이스 패턴, 쿼리 최적화, 분석 및 데이터 엔지니어링 모범 사례.",
    "Claude Code 세션에서 재사용 가능한 패턴을 자동으로 추출하여 향후 사용을 위한 학습된 스킬로 저장합니다.",
    "평가 주도 개발(EDD) 원칙을 구현하는 Claude Code 세션용 공식 평가 프레임워크",
    "임의의 자동 컴팩션 대신 논리적 간격에서 수동 컨텍스트 압축을 제안하여 작업 단계를 통해 컨텍스트를 보존합니다.",
    "Claude Code 세션을 위한 포괄적인 검증 시스템.",
])
def test_supplied_korean_true_positive_is_retained(description):
    assert detect(description) == "ko"
    assert normalize(description) == description
    config = AgentConfig(kind="skill", skill=SkillMeta(
        name="korean-skill", dir_name="korean-skill", description=description,
        name_line=2, description_line=3,
    ))
    findings = [finding for finding in _detect_skill_metadata(config) if finding.code == "H1.8"]
    assert len(findings) == 1
    assert findings[0].evidence == description[:120]


@pytest.mark.parametrize("description", [
    # u-4523f71beaef, security-review, FP / ESCALATE in the frozen corpus.
    "인증 추가, 사용자 입력 처리, 시크릿 관리, API 엔드포인트 생성, 결제/민감한 기능 구현 시 이 스킬을 사용하세요. 포괄적인 보안 체크리스트와 패턴을 제공합니다.",
    # u-eed217343bb1, tdd-workflow, FP / ESCALATE in the frozen corpus.
    "새 기능 작성, 버그 수정 또는 코드 리팩터링 시 이 스킬을 사용하세요. 단위, 통합, E2E 테스트를 포함한 80% 이상의 커버리지로 테스트 주도 개발을 시행합니다.",
])
def test_mined_korean_directive_reaches_existing_english_gate(description):
    assert detect(description) == "ko"
    assert not _SKILL_TRIGGER.search(description)
    assert _SKILL_TRIGGER.search(normalize(description))
    config = AgentConfig(kind="skill", skill=SkillMeta(
        name="korean-skill", dir_name="korean-skill", description=description,
        name_line=2, description_line=3,
    ))
    assert not any(finding.code == "H1.8" for finding in _detect_skill_metadata(config))


@pytest.mark.parametrize("description", [
    "새 기능 작성 시 이 스킬을 사용하지 마세요. 다른 도구를 선택하세요.",
    "새 기능 작성 시 이 스킬을 사용하지 않습니다. 다른 도구를 선택합니다.",
    "새 기능 작성 시 이 스킬을 사용하세요라고 말하지 마세요. 다른 도구를 선택하세요.",
    "새 기능 작성 시 이 스킬을 사용하세요? 다른 도구를 선택해야 하나요?",
    "예시 이 스킬을 사용하세요. 설명에 포함된 문장으로서 실행 조건은 없습니다.",
    "새 기능 작성 시 이 스킬을 사용하여 테스트를 생성한 결과를 저장했습니다.",
])
def test_korean_negations_questions_and_methods_do_not_become_triggers(description):
    assert normalize(description) == description
    assert not _SKILL_TRIGGER.search(description)
