import os
import time
import random
import re
import json
from datetime import datetime
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage, BaseMessage

class Agent:
    """A representation of an agent within the chat system."""

    shared_memory = {}

    def __init__(self, name, role, model):
        self.name = name
        self.role = role
        self.model = model
        self.system_message = self._get_system_messages_for(name)
        self.knowledge_base = self._get_knowledge_base_for(role)
        self.stored_messages = [self.system_message]
        self.history = []
        self.keyword_memory = {}

    @classmethod
    def set_initial_context(cls, incident_description):
        """Set the initial context for the agent."""

        template = f"""
        Incident: {incident_description}
        Ben: As the CEO of the company, Ben is responsible for the overall vision and direction of the company. He focuses on high-level decisions, managing company resources, building partnerships, and maintaining company culture. Ben often interacts with stakeholders, partners, and the media.

        Tyne: Tyne, as the Chief Technical Officer, oversees all technical operations and strategies of the company. This includes software development, infrastructure, and cybersecurity. Tyne works closely with the technical teams to ensure projects are on track and the company's technical goals are achieved.

        Da: Da is the technical assistant responsible for actual deployments, updates, and hands-on technical tasks. He implements the strategies set by Tyne and often troubleshoots technical issues, ensuring smooth operations. Da is the go-to for understanding the specifics of any technical incident.

        Instructions for Chat Model:
        1. Always respond from the perspective of the addressed agent.
        2. Avoid prefixing other agent names in the response.

        You are now role-playing as these three characters. The user is the incident manager who will seek to collaborate with you to solve the Incident. Respond as the respective person based on the user's input. Remember your roles.
        """.format(incident_description=incident_description)
        cls.current_context = template

    def _get_knowledge_base_for(self, role):
        """Retrieve the knowledge base for the agent's role."""

        with open('./knowledge_base.json', 'r') as f:
            knowledge_bases = json.load(f)
        return knowledge_bases.get(role, {})

    def _get_system_messages_for(self, role):
        """Generate a system message for the agent."""

        default_messages = {
            "Ben": "Hello, I'm Ben, the CEO.",
            "Tyne": "Hey there, Tyne here - the CTO.",
            "Da": "Hi! I'm Da, your trusty technical assistant."
        }
        recent_actions = Agent.shared_memory.get(role, "")
        return SystemMessage(content=f"{default_messages.get(role, '')} {recent_actions}")

    def bid(self, message: HumanMessage) -> int:
        """Generate a bid value for the given message."""

        bid_value = 0
        for keyword in self.knowledge_base['keywords']:
            if keyword in message.content:
                bid_value += 5
                if keyword in self.keyword_memory:
                    self.keyword_memory[keyword] += 1
                    if self.keyword_memory[keyword] > 3:
                        bid_value -= 2
                else:
                    self.keyword_memory[keyword] = 1
        for keyword in ["urgent", "asap", "immediately"]:
            if keyword in message.content:
                bid_value += 10
        return bid_value

    def step(self, input_message: HumanMessage) -> AIMessage:
        """Process an input message and produce an output message."""

        Agent.current_context += "\nUser: " + input_message.content

        try:
            raw_output = self.model([HumanMessage(content=Agent.current_context)])
            parsed_output = raw_output.content.split("User: " + input_message.content)[-1].strip()

            if parsed_output.startswith(self.name + ":"):
                parsed_output = parsed_output[len(self.name) + 1:].strip()

            output_message = AIMessage(content=parsed_output)
        except Exception as e:
            print(f"Error: {str(e)}")
            output_message = AIMessage(content="Sorry, I encountered an error. Please try again.")

        Agent.current_context += "\n" + self.name + ": " + output_message.content
        Agent.shared_memory[input_message.content] = output_message.content
        self.stored_messages.append(output_message)
        self.history.append((input_message, output_message))
        return output_message

class CommunicationManager:
    """Manages the communication between the user and the agents."""

    def __init__(self, agents):
        self.agents = agents

    @staticmethod
    def get_incident_description():
        """Randomly select an incident description."""

        incidents = [
            {"desc": "A recent update by Da to the data pipeline is causing our recommendation models to malfunction. Users are seeing unrelated product suggestions.", "severity": "High"},
            {"desc": "There's an anomaly in the way data is being stored post a change committed by Da. Our database integrity might be compromised.", "severity": "Medium"},
            {"desc": "The recent machine learning model version deployed by Da to the prod environment is behaving erratically, affecting our predictive capabilities.", "severity": "Low"}
        ]
        return random.choice(incidents)["desc"], random.choice(incidents)["severity"]

    def print_message(self, role_name, message):
        """Display a message to the console."""

        current_time = datetime.now().strftime('%H:%M:%S')
        print(f"{current_time} - {role_name}: {message}\n")
        time.sleep(1)

    def run_simulation(self):
        """Run the chat simulation."""
        chosen_incident, severity = self.get_incident_description()
        print(f"Incident report (Severity: {severity}): {chosen_incident}\n")
        time.sleep(1.5)

        for agent in self.agents.values():
            self.print_message(agent.role, agent.system_message.content)

        while True:
            user_input = input("Incident Manager (You): ")

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting chat system...")
                break
            elif user_input.lower() in ["list all agents"]:
                for agent in self.agents.values():
                    print(f"{agent.name} - {agent.role}")
                continue
            elif "what's your focus" in user_input.lower():
                agent_name = user_input.split()[-1]
                if agent_name in self.agents:
                    print(self.agents[agent_name].knowledge_base['focus'])
                continue

            incident_message = HumanMessage(content=user_input)

            if user_input in Agent.shared_memory:
                self.print_message("System", f"Previously addressed: {Agent.shared_memory[user_input]}")
                continue

            addressed_agent = None
            for agent_name, agent in self.agents.items():
                if re.search(f"\\b{agent_name}\\b", user_input, re.IGNORECASE):
                    addressed_agent = agent_name
                    break

            if addressed_agent:
                response = self.agents[addressed_agent].step(incident_message)
                self.print_message(addressed_agent, response.content)
            else:
                bids = {agent_name: agent.bid(incident_message) for agent_name, agent in self.agents.items()}
                responding_agent_name = max(bids, key=bids.get)
                response = self.agents[responding_agent_name].step(incident_message)
                self.print_message(responding_agent_name, response.content)

if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY"
    llm = ChatOpenAI(model_name='gpt-4')

    agents = {
        "Ben": Agent("Ben", "CEO", llm),
        "Tyne": Agent("Tyne", "CTO", llm),
        "Da": Agent("Da", "Assistant", llm)
    }

    chosen_incident, _ = CommunicationManager.get_incident_description()
    for agent in agents.values():
        agent.set_initial_context(chosen_incident)

    manager = CommunicationManager(agents)
    manager.run_simulation()