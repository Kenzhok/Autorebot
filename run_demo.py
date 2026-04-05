from server.code_review_env_environment import CodeReviewEnvironment
from agent import LLMAgent

env = CodeReviewEnvironment()
agent = LLMAgent()

obs = env.reset(difficulty="all")

total_reward = 0
correct = 0
total = 0
step = 0

print("\n🚀 Starting Code Review Simulation\n")

while not obs.done:
    step += 1
    print(f"\n--- Step {step} ---")

    action = agent.act(obs)
    print(f"Agent Action: {action.action_type}")

    obs = env.step(action)

    print(f"Reward: {obs.reward}")
    print(f"Done: {obs.done}")

    # Learning step
    agent.learn(action, obs)

    total_reward += obs.reward

    # Accuracy tracking
    total += 1
    if obs.reward > 0:
        correct += 1

print("\n✅ Episode Finished")
print(f"Total Reward: {total_reward}")
print(f"Accuracy: {correct}/{total} = {correct/total:.2f}")
