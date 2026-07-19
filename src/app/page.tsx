import ContactLinks from "@/components/contact/ContactLinks";
import HeroGrid from "@/components/hero/HeroGrid";
import ProjectGrid from "@/components/projects/ProjectGrid";
import SectionWrapper from "@/components/SectionWrapper";
import CertificationList from "@/components/section-catalog/CertificationList";
import GitHubActivity from "@/components/section-catalog/GitHubActivity";
import ImpactGrid from "@/components/section-catalog/ImpactGrid";
import OpenSourceGrid from "@/components/section-catalog/OpenSourceGrid";
import ProductCatalog from "@/components/section-catalog/ProductCatalog";
import ProfilePanel from "@/components/section-catalog/ProfilePanel";
import QuestionGrid from "@/components/section-catalog/QuestionGrid";
import SkillMatrix from "@/components/section-catalog/SkillMatrix";
import Timeline from "@/components/work/Timeline";
import { answerHub, contactLinks, experienceData, heroData, portfolioFaq, projectsData, workGuide } from "@/data/portfolio";
import { getAppCatalog, getExtensionCatalog } from "@/lib/content";

export default async function Home() {
  const [apps, extensions] = await Promise.all([getAppCatalog(), getExtensionCatalog()]);

  return (
    <main id="main-content" className="page-main" aria-label="Senior Android engineer portfolio of Michael Samuel Naeem">
      <HeroGrid data={heroData} />
      <SectionWrapper id="about" heading="About" headingId="about-heading">
        <ProfilePanel />
      </SectionWrapper>
      <SectionWrapper id="answers" heading="Hiring Questions" headingId="answers-heading">
        <QuestionGrid items={answerHub} />
      </SectionWrapper>
      <SectionWrapper id="impact" heading="Measured Outcomes" headingId="impact-heading">
        <ImpactGrid />
      </SectionWrapper>
      <SectionWrapper id="projects" heading="Selected Work" headingId="projects-heading">
        <ProjectGrid projects={projectsData} />
      </SectionWrapper>
      <SectionWrapper id="apps" heading={`Published Android Apps (${apps.length})`} headingId="apps-heading">
        <ProductCatalog items={apps} kind="apps" />
      </SectionWrapper>
      <SectionWrapper id="vscode" heading={`VS Code Extensions (${extensions.length})`} headingId="vscode-heading">
        <ProductCatalog items={extensions} kind="vscode" />
      </SectionWrapper>
      <SectionWrapper id="opensource" heading="Open Source" headingId="opensource-heading">
        <OpenSourceGrid />
      </SectionWrapper>
      <SectionWrapper id="github-activity" heading="GitHub Activity" headingId="github-activity-heading">
        <GitHubActivity />
      </SectionWrapper>
      <SectionWrapper id="skills" heading="Skills" headingId="skills-heading">
        <SkillMatrix />
      </SectionWrapper>
      <SectionWrapper id="experience" heading="Experience" headingId="experience-heading">
        <Timeline experience={experienceData} />
      </SectionWrapper>
      <SectionWrapper id="certifications" heading="Certifications" headingId="certifications-heading">
        <CertificationList />
      </SectionWrapper>
      <SectionWrapper id="work-together" heading="How We Can Work Together" headingId="work-together-heading">
        <QuestionGrid items={workGuide} />
      </SectionWrapper>
      <SectionWrapper id="faq" heading="Frequently Asked Questions" headingId="faq-heading">
        <QuestionGrid items={portfolioFaq} />
      </SectionWrapper>
      <SectionWrapper id="contact" heading="Contact" headingId="contact-heading">
        <ContactLinks email={heroData.email} links={contactLinks} />
      </SectionWrapper>
    </main>
  );
}
