"""
AI 메일 비서 성능 평가 모듈

이 모듈은 다음을 제공합니다:
- 성능 평가 시스템 (PerformanceEvaluator)
- 테스트 데이터셋 생성기 (DatasetGenerator)
- 평가 실행 스크립트 (run_evaluation.py)
"""

from .performance_evaluator import (
    PerformanceEvaluator,
    AnalysisEvaluation,
    ReplyEvaluation,
    SummaryEvaluation,
    evaluator,
    create_ground_truth_template
)

from .dataset_generator import (
    DatasetGenerator,
    dataset_generator
)

__all__ = [
    # 평가 클래스
    'PerformanceEvaluator',
    'AnalysisEvaluation',
    'ReplyEvaluation',
    'SummaryEvaluation',
    'evaluator',
    'create_ground_truth_template',

    # 데이터셋 생성
    'DatasetGenerator',
    'dataset_generator',
]
