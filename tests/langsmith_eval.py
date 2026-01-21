import os
import pandas as pd
from langsmith import Client
from langsmith.evaluation import evaluate, LangChainStringEvaluator
from langchain_openai import ChatOpenAI

# 1. 설정 (API Key는 환경변수로 설정되어 있다고 가정하거나 직접 입력 필요)
# os.environ["LANGCHAIN_API_KEY"] = "ls__..."
# os.environ["OPENAI_API_KEY"] = "sk-..."

# 2. 데이터셋 생성 (또는 기존 데이터셋 사용)
client = Client()
dataset_name = "Email Writing Test"

# 예제 데이터: 입력(input)과 기대하는 출력(reference)
examples = [
    ("Write a polite email declining a meeting.", "Dear [Name], Thank you for the invitation. Unfortunately, I cannot attend..."),
    ("Write a rude email declining a meeting.", "No, I won't come. Stop asking."),
]

# 데이터셋이 없으면 생성
if not client.has_dataset(dataset_name=dataset_name):
    dataset = client.create_dataset(dataset_name=dataset_name, description="Email writing tone test")
    for input_text, ref_text in examples:
        client.create_example(
            inputs={"prompt": input_text},
            outputs={"reference": ref_text},
            dataset_id=dataset.id,
        )

# 3. 평가 대상 모델 정의
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def target_model(inputs):
    return llm.invoke(inputs["prompt"]).content

# 4. 평가자(Evaluator) 정의
# 4.1. 정확도/유사도 평가 (내장 평가자 사용)
qa_evaluator = LangChainStringEvaluator("cot_qa") # Context based QA evaluator

# 4.2. 커스텀 채점 로직 (예: 'polite' 단어가 들어갔는지)
def politeness_evaluator(run, example):
    prediction = run.outputs["output"]
    score = 1 if "thank you" in prediction.lower() else 0
    return {"key": "politeness_score", "score": score}

# 5. 평가 실행
results = evaluate(
    target_model,
    data=dataset_name,
    evaluators=[qa_evaluator, politeness_evaluator],
    experiment_prefix="email-test-v1",
)

print(results)
