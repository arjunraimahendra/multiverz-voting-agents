from typing import List, Dict, Any, TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel
# from IPython.display import Image, display
# from dotenv import load_dotenv
# load_dotenv()


# from models.models import (
#     Category,
#     Idea,
#     ProjectIdeas,
#     Rating,
#     Agent,
#     AgentRatings
# )

from prompts import (
    business_agent_system_prompt,
    finance_agent_system_prompt,
    geo_political_agent_system_prompt,
    impact_assessment_agent_system_prompt,
    implementation_agent_system_prompt,
    innovation_agent_system_prompt,
    regulatory_agent_system_prompt,
    sustainability_agent_system_prompt,
    technology_agent_system_prompt,
)

# Define agent mappings and prompts
AGENT_MAPPING = {
    1: {
        "name": "Innovation Agent",
        "prompt": innovation_agent_system_prompt
    },
    2: {
        "name": "Implementation Expert",
        "prompt": implementation_agent_system_prompt
    },
    3: {
        "name": "Finance Agent",
        "prompt": finance_agent_system_prompt
    },
    4: {
        "name": "Impact Assessment Agent",
        "prompt": impact_assessment_agent_system_prompt
    },
    5: {
        "name": "Technology Agent",
        "prompt": technology_agent_system_prompt
    },
    6: {
        "name": "Business Agent",
        "prompt": business_agent_system_prompt
    },
    7: {
        "name": "Regulatory Agent",
        "prompt": regulatory_agent_system_prompt
    },
    8: {
        "name": "Sustainability Agent",
        "prompt": sustainability_agent_system_prompt
    },
    9: {
        "name": "Geopolitical Agent",
        "prompt": geo_political_agent_system_prompt
    }
}



#############################
# Input Validation
#############################

class Category(BaseModel):
   model_config = ConfigDict(
      extra="ignore",
   )
   name: str

class Idea(BaseModel):
   model_config = ConfigDict(
      extra="ignore",
   )
   id_: int = Field(validation_alias="id", serialization_alias="id")
   title: str
   summary: str
   categories: list[Category]

class ProjectIdeas(BaseModel):
   model_config = ConfigDict(
      extra="ignore",
      alias_generator=to_camel,
    )
   agents: list[int]
   project_name: str
   project_description: str
   ideas: list[Idea]


#############################
# Output Validation
#############################
class Rating(BaseModel):
    ideaId: int
    rating: int
    comment: str

class Agent(BaseModel):
    agentId: int
    agentName: str
    ratings: List[Rating]

class AgentRatings(BaseModel):
    agents: List[Agent]


#############################
# Validation End
#############################


# Define the state structure
class GraphState(TypedDict):
    project_ideas_input: ProjectIdeas
    input_json: str
    output: AgentRatings
    error: str | None

# Initialize LLM (you can replace with your preferred model)
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# Structured Output
class IdeaRating(BaseModel):
    rating: int
    comment: str

rating_llm = llm.with_structured_output(IdeaRating)


def validate_input(state: GraphState) -> Command[Literal["run_agents", "__end__"]]:
    print(" ========= Validate Input ========= ")
    try:
        project_ideas = ProjectIdeas.model_validate_json(state["input_json"])
        print("Validated Successful:", project_ideas)
        return Command(
            goto="run_agents",
            update={"project_ideas_input": project_ideas}
        )
    except ValidationError as e:
        print("Validation error:", e)
        return Command(
            goto=END,
            update={"error": str(e)}
        )

def run_agents(state: GraphState) -> Command[Literal["__end__"]]:

    agent_outputs = {"agents": []}

    for agent_id in state["project_ideas_input"].agents:
        rating_ideas_list = []
        agent_info = AGENT_MAPPING[agent_id]

        for idea in state["project_ideas_input"].ideas:
            agent_prompt=agent_info["prompt"].format(
                project_name=state["project_ideas_input"].project_name,
                project_description=state["project_ideas_input"].project_description,
                idea_title=idea.title,
                idea_summary=idea.summary,
                idea_categories= ', '.join([category.name for category in idea.categories if category])
            )

            rating_output = rating_llm.invoke(agent_prompt)
            # print("Rating LLM output: ", rating_output.model_dump_json(indent=2))
            
            rating_ideas_list.append(Rating(
                    ideaId=idea.id_,
                    rating=rating_output.rating,
                    comment=rating_output.comment
                )
            )
        agent_outputs["agents"].append(Agent(
            agentId=agent_id,
            agentName=agent_info["name"],
            ratings=rating_ideas_list,
        ))
        # print("Agent output: ", agent_outputs["agents"][-1].model_dump_json(indent=2))

    # print("All agent outputs: ", agent_outputs)

    return Command(
        goto=END,
        update={"output": AgentRatings.model_validate(agent_outputs)}
    )
    


# Construct the graph: here we put everything together to construct our graph
builder = StateGraph(GraphState)
builder.add_node("run_agents", run_agents)
builder.add_node("validate_input", validate_input)
builder.add_edge(START, "validate_input")
# builder.add_edge("validate_input", "run_agents")
# builder.add_edge("run_agents", END)

# Compile the graph
graph = builder.compile()
