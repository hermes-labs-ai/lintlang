"""The supplied Korean cohort has no reliable FP-only activation phrase.

These seven genuine missing-trigger descriptions keep their H1.8 findings.
The generic purpose marker 위한 also occurs in the topic-only Korean FP's
feature announcement, so mapping that marker would erase genuine findings.
"""

import pytest

from lintlang.detectors.h1 import _detect_skill_metadata
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
