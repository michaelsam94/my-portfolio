import "./ConversationalGuide.css";

const prompts = [
  {
    question: "What should you send me first?",
    answer:
      "Send the product goal, affected users, current stack, deadline, and any screenshots, crash logs, store reviews, or short recording.",
  },
  {
    question: "How do I usually work with a team?",
    answer:
      "We agree on the outcome, map the riskiest parts, and choose the smallest useful milestone before writing more code.",
  },
  {
    question: "What will I tell you if something is risky?",
    answer:
      "I will say it plainly, explain the risk, and suggest a practical path if the scope, architecture, or timeline looks fragile.",
  },
  {
    question: "Can I join an existing engineering team?",
    answer:
      "Yes. I can pair with your team, review pull requests, lead a feature stream, or help Android, React, and backend work connect.",
  },
  {
    question: "Do we need a long contract to start?",
    answer:
      "No. We can start with a focused audit, small build, rescue sprint, or advisory call, then expand only if the fit is good.",
  },
  {
    question: "What result should you expect?",
    answer:
      "You should expect clearer decisions, cleaner code, fewer surprises, and software that is easier to ship and maintain.",
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
