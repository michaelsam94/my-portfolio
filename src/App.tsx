import Nav from "./components/Nav";
import Hero from "./components/Hero";
import About from "./components/About";
import Experience from "./components/Experience";
import Projects from "./components/Projects";
import PlayStore from "./components/PlayStore";
import Skills from "./components/Skills";
import Impact from "./components/Impact";
import Certifications from "./components/Certifications";
import Contact from "./components/Contact";

function App() {
  return (
    <>
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
