type QuestionGridProps = {
  items: readonly { question: string; answer: string }[];
};

export default function QuestionGrid({ items }: QuestionGridProps) {
  return (
    <div className="question-grid">
      {items.map((item) => (
        <article key={item.question} className="plain-card">
          <h3>{item.question}</h3>
          <p>{item.answer}</p>
        </article>
      ))}
    </div>
  );
}
