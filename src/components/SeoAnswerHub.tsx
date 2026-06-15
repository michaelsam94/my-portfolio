import "./SeoAnswerHub.css";

const answers = [
  {
    question: "What kind of software engineer is Michael Samuel Naeem?",
    answer:
      "Michael Samuel Naeem is a senior Android, Kotlin, Jetpack Compose, React, and TypeScript engineer with 10+ years of software engineering experience and 4+ years leading engineers across mobile apps, commerce, EV charging, OCPP systems, and AI-assisted developer tooling.",
  },
  {
    question: "Can Michael work with remote teams in the United States or Europe?",
    answer:
      "Yes. Michael is based in Cairo, Egypt and works with remote product and engineering teams across the United States, Europe, the Gulf region, and worldwide time zones for full-time, contract, and freelance software development.",
  },
  {
    question: "What services can teams hire Michael for?",
    answer:
      "Teams can hire Michael for Android app development, Kotlin and Jetpack Compose architecture, React and TypeScript interfaces, OCPP and EV charging software, AI automation, technical leadership, 20% API-response improvements, and production performance optimization.",
  },
  {
    question: "What proof of experience does the portfolio show?",
    answer:
      "The portfolio highlights 10+ years of software engineering, 4+ years leading engineers, 120k+ commerce users supported, 240+ merchants enabled, 99.9% uptime ownership, 50k+ app users reached, published Google Play apps, VS Code extensions, and applied AI/OCPP systems.",
  },
  {
    question: "Which outcomes has Michael delivered?",
    answer:
      "Reported outcomes include 70% faster store operations, 50% faster vendor onboarding, 30% lower crash rate across production mobile releases, 20% faster API responses, and 4-6 second EV charging session setup targets.",
  },
  {
    question: "How should recruiters or founders contact Michael?",
    answer:
      "Recruiters, founders, and engineering leaders can contact Michael through LinkedIn at linkedin.com/in/michaelsam00, GitHub at github.com/michaelsam94, or by email at michaelsam00@yahoo.com.",
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
        <p className="answer-hub__eyebrow">Hire Michael Samuel Naeem</p>
        <h2 id="answer-hub-title">
          Senior Android, Kotlin, React, OCPP, and AI automation engineer with
          10+ years of measured delivery.
        </h2>
        <p className="answer-hub__summary">
          Michael builds production mobile and web software, leads engineering
          delivery, and helps teams ship reliable products across Android,
          Jetpack Compose, React, TypeScript, EV charging protocols, and
          AI-powered workflow automation, with outcomes including 120k+ users,
          99.9% uptime ownership, and 70% faster operations.
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
