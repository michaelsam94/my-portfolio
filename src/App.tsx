import Nav from "./components/Nav";
import Hero from "./components/Hero";
import StructuredData from "./components/StructuredData";
import SkillsStructuredData from "./components/SkillsStructuredData";
import About from "./components/About";
import Experience from "./components/Experience";
import Projects from "./components/Projects";
import PlayStore from "./components/PlayStore";
import Skills from "./components/Skills";
import Impact from "./components/Impact";
import Certifications from "./components/Certifications";
import Contact from "./components/Contact";
import CustomCursor from "./components/CustomCursor";

function App() {
  return (
    <>
      <CustomCursor />
      <StructuredData />
      <SkillsStructuredData />
      <Nav />
      <main id="main-content" aria-label="Michael Samuel Naeem portfolio — Android developer, mobile engineer, technical lead">
        <Hero />
        <About />
        <Experience />
        <Projects />
        <PlayStore />
        <Impact />
        <Skills />
        <Certifications />
        <Contact />
      </main>
    </>
  );
}

export default App;
