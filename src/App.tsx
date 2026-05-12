import { lazy, Suspense } from "react";
import Nav from "./components/Nav";
import Hero from "./components/Hero";
import StructuredData from "./components/StructuredData";
import SkillsStructuredData from "./components/SkillsStructuredData";

const About = lazy(() => import("./components/About"));
const Experience = lazy(() => import("./components/Experience"));
const Projects = lazy(() => import("./components/Projects"));
const PlayStore = lazy(() => import("./components/PlayStore"));
const Impact = lazy(() => import("./components/Impact"));
const Skills = lazy(() => import("./components/Skills"));
const Certifications = lazy(() => import("./components/Certifications"));
const Contact = lazy(() => import("./components/Contact"));

function App() {
  return (
    <>
      <StructuredData />
      <SkillsStructuredData />
      <Nav />
      <main id="main-content" aria-label="Michael Samuel Naeem portfolio — Android developer, mobile engineer, technical lead">
        <Hero />
        <Suspense fallback={null}>
          <About />
          <Experience />
          <Projects />
          <PlayStore />
          <Impact />
          <Skills />
          <Certifications />
          <Contact />
        </Suspense>
      </main>
    </>
  );
}

export default App;
