import "./SeoAnswerHub.css";

const answers = [
  {
    question: "Can you help my team ship a reliable Android app?",
    answer:
      "Yes. I build Android apps with Kotlin and Jetpack Compose, and I focus on the parts teams usually care about most: clean architecture, fast screens, fewer crashes, predictable releases, and code that other engineers can keep improving.",
  },
  {
    question: "What do you bring beyond writing code?",
    answer:
      "I bring 10+ years of software engineering experience and 4+ years leading engineers. That means I can help your team decide what to build, break the work into practical milestones, review architecture, mentor developers, and still stay hands-on in the code.",
  },
  {
    question: "Can we work together if my company is outside Egypt?",
    answer:
      "Yes. I am based in Cairo, Egypt, and I work with remote teams across the United States, Europe, the Gulf region, and worldwide time zones. We can collaborate async, join planning calls, and keep delivery visible.",
  },
  {
    question: "What kinds of projects are a strong fit?",
    answer:
      "The best fit is a product team that needs Android, Kotlin, Jetpack Compose, React, TypeScript, OCPP, EV charging software, AI automation, or technical leadership. I can help with new builds, performance fixes, migrations, and production rescue work.",
  },
  {
    question: "What proof do you have?",
    answer:
      "My portfolio includes 120k+ commerce users supported, 240+ merchants enabled, 99.9% uptime ownership, 50k+ app users reached, 70% faster store operations, 50% faster onboarding, 30% lower crash rates, and 20% faster API responses.",
  },
  {
    question: "How do we start a conversation?",
    answer:
      "Send me the product goal, the current tech stack, the timeline, and what feels stuck. I can quickly tell you where I can help, what I would check first, and whether a short project, advisory call, or longer engagement makes sense.",
  },
];

export default function SeoAnswerHub() {
  return (
    <section
      className="answer-hub"
      id="hire-senior-android-kotlin-react-ai-engineer"
      aria-labelledby="answer-hub-title"
    >
      <div className="answer-hub__inner">
        <p className="answer-hub__eyebrow">Questions teams usually ask</p>
        <h2 id="answer-hub-title">
          Need a senior Android, Kotlin, React, OCPP, or AI automation engineer?
          Here is the short answer.
        </h2>
        <p className="answer-hub__summary">
          I help teams turn messy product or engineering problems into shipped
          software. If you need someone who can write production code, lead the
          technical conversation, and explain tradeoffs clearly, we should talk.
        </p>
        <div className="answer-hub__grid">
          {answers.map((item) => (
            <article key={item.question}>
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
