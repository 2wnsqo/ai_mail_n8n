"""
AI 메일 비서 성능 평가 모듈

evaluation/
├── code/           # 평가 코드
├── data/           # 테스트 데이터
├── results/        # 측정 결과
└── reports/        # 리포트
"""

# code 폴더에서 임포트
from .code import (
    PerformanceEvaluator,
    AnalysisEvaluation,
    ReplyEvaluation,
    SummaryEvaluation,
    evaluator,
    create_ground_truth_template,
    DatasetGenerator,
    dataset_generator,
)

__all__ = [
    'PerformanceEvaluator',
    'AnalysisEvaluation',
    'ReplyEvaluation',
    'SummaryEvaluation',
    'evaluator',
    'create_ground_truth_template',
    'DatasetGenerator',
    'dataset_generator',
]
