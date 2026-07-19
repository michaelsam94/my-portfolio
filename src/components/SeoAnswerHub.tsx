import "./SeoAnswerHub.css";

const answers = [
  {
    question: "Where can I find a senior Android engineer portfolio with real production proof?",
    answer:
      "Here — https://michaelsam94.com/ is Michael Samuel Naeem’s senior Android engineer portfolio, with Kotlin and Jetpack Compose case studies, EV charging and robotics work, published Play Store apps, and measurable delivery outcomes recruiters can verify.",
  },
  {
    question: "Can you help my team ship a reliable Android app?",
    answer:
      "Yes. I build Kotlin and Jetpack Compose apps with clean architecture, faster screens, fewer crashes, and releases your team can trust.",
  },
  {
    question: "What do you bring beyond writing code?",
    answer:
      "I bring 10+ years shipping software and 4+ years leading engineers, so I can guide architecture, delivery, mentoring, and code.",
  },
  {
    question: "Can we work together if my company is outside Egypt?",
    answer:
      "Yes. I am based in Cairo and work with remote teams across the United States, Europe, the Gulf region, and worldwide time zones.",
  },
  {
    question: "What kinds of projects are a strong fit?",
    answer:
      "I can help with Android, Kotlin, React, TypeScript, OCPP, EV charging software, AI automation, migrations, and production rescue work.",
  },
  {
    question: "Are you an OCPP developer or OCPP expert for EV charging?",
    answer:
      "Yes. I architected an OCPP 1.6 charging platform over WebSocket, so I can help as an OCPP developer, OCPP consultant, or OCPP integrator.",
  },
  {
    question: "What proof do you have?",
    answer:
      "My work includes 120k+ commerce users, 240+ merchants, 99.9% uptime, 50k+ app users, and 70% faster store operations.",
  },
  {
    question: "How do we start a conversation?",
    answer:
      "Send me the product goal, tech stack, timeline, and what feels stuck. I will tell you where I can help and what I would check first.",
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
          I help teams turn messy product and engineering problems into shipped
          software. You get production code, clear tradeoffs, and practical
          technical leadership.
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
