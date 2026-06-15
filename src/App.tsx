import Nav from "./components/Nav";
import Hero from "./components/Hero";
import SeoAnswerHub from "./components/SeoAnswerHub";
import ConversationalGuide from "./components/ConversationalGuide";
import StructuredData from "./components/StructuredData";
import SkillsStructuredData from "./components/SkillsStructuredData";
import SeoKnowledgeGraph from "./components/SeoKnowledgeGraph";
import DeferredPortfolioSections from "./components/DeferredPortfolioSections";

function App() {
  return (
    <>
      <StructuredData />
      <SkillsStructuredData />
      <SeoKnowledgeGraph />
      <Nav />
      <main id="main-content" aria-label="Michael Samuel Naeem portfolio — Android developer, mobile engineer, technical lead">
      <Hero />
      <SeoAnswerHub />
      <ConversationalGuide />
        <DeferredPortfolioSections />
      </main>
    </>
  );
}

export default App;
