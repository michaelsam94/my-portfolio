type QuestionGridProps = {
  items: readonly { question: string; answer: string }[];
};

export default function QuestionGrid({ items }: QuestionGridProps) {
  return (
    <div className="question-grid">
      {items.map((item) => (
        <article key={item.question} className="plain-card">
<div className="plain-card-title">{item.question}</div>
          <p>{item.answer}</p>
        </article>
      ))}
    </div>
  );
}
