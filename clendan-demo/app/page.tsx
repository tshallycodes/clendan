import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Hero } from "@/components/sections/Hero";
import { ProblemStatement } from "@/components/sections/ProblemStatement";
import { WorkerShowcase } from "@/components/sections/WorkerShowcase";
import { ApiToolsStrip } from "@/components/sections/ApiToolsStrip";
import { IntegrationStrip } from "@/components/sections/IntegrationStrip";
import { CtaBanner } from "@/components/sections/CtaBanner";

export default function LandingPage() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <ProblemStatement />
        <WorkerShowcase />
        <ApiToolsStrip />
        <IntegrationStrip />
        <CtaBanner />
      </main>
      <Footer />
    </>
  );
}
