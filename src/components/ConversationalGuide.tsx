import "./ConversationalGuide.css";

const prompts = [
  {
    question: "What should you send me first?",
    answer:
      "Send me the product goal, the users affected, the current stack, and the deadline. If you have screenshots, crash logs, store reviews, or a short Loom, even better.",
  },
  {
    question: "How do I usually work with a team?",
    answer:
      "We agree on the outcome, I map the riskiest parts, then we choose the smallest useful milestone. You get clear tradeoffs, visible progress, and production-minded decisions.",
  },
  {
    question: "What will I tell you if something is risky?",
    answer:
      "I will say it plainly. If the scope is too big, the architecture is fragile, or the timeline is unrealistic, I will explain the risk and suggest a practical path forward.",
  },
  {
    question: "Can I join an existing engineering team?",
    answer:
      "Yes. I can pair with your team, review pull requests, lead a feature stream, stabilize releases, or help your Android, React, and backend engineers move faster together.",
  },
  {
    question: "Do we need a long contract to start?",
    answer:
      "No. We can start with a focused audit, a small build, a rescue sprint, or a technical advisory call. If the fit is good, we can expand from there.",
  },
  {
    question: "What result should you expect?",
    answer:
      "You should expect clearer decisions, cleaner code, fewer surprises, and software that is easier to ship, measure, and maintain after the first release.",
  },
];

export default function ConversationalGuide() {
  return (
    <section
      id="how-we-can-work-together"
      className="conversation-section"
      aria-labelledby="conversation-title"
    >
      <div className="conversation-heading">
        <p className="section-kicker">How we can work together</p>
        <h2 id="conversation-title" className="section-title">
          Plain answers before we start
        </h2>
        <p>
          If you are deciding whether I can help, these are the questions I
          would want answered quickly too.
        </p>
      </div>

      <div className="conversation-grid">
        {prompts.map((prompt) => (
          <article className="conversation-card" key={prompt.question}>
            <h3>{prompt.question}</h3>
            <p>{prompt.answer}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
