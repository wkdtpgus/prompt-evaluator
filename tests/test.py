from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

OPENAI_MODEL = "gpt-3.5-turbo"

execution_llm = ChatOpenAI(
    model=OPENAI_MODEL,
)

messages = [
    ("system", "Extract Nouns of Location Name from the context"),
    (
        "user",
        """
음바페는 26일 쿠프 드 프랑스(프랑스컵) 올랭피크 리옹과의 결승전에서 풀타임을 뛰며 2-1로 팀 승리를 도왔다. 
3년 만에 대회 정상에 오른 PSG는 역대 최다 15회 우승으로 2위 마르세유(10회)를 멀찍이 따돌렸다. 
음바페는 이날 경기로 PSG에서의 커리어를 마무리했다. 음바페는 7시즌 동안 공식전 308경기 256골의 성적을 남기고 PSG를 떠난다.
""",
    ),
]

response = execution_llm.invoke(messages)

print(response.content)
