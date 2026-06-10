import Nav from "./components/Nav";
import Hero from "./components/Hero";
import StructuredData from "./components/StructuredData";
import SkillsStructuredData from "./components/SkillsStructuredData";
import DeferredPortfolioSections from "./components/DeferredPortfolioSections";

function App() {
  return (
    <>
      <StructuredData />
      <SkillsStructuredData />
      <Nav />
      <main id="main-content" aria-label="Michael Samuel Naeem portfolio — Android developer, mobile engineer, technical lead">
        <Hero />
        <DeferredPortfolioSections />
      </main>
    </>
  );
}

export default App;
