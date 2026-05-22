"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_LINKS } from "@/lib/constants";

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed top-0 left-0 right-0 z-40 transition-all duration-200",
        scrolled
          ? "border-b border-brand-border bg-brand-bg/95 backdrop-blur-sm"
          : "bg-transparent"
      )}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8 flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <span className="w-7 h-7 rounded-sm border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-sm">
            C
          </span>
          <span className="font-heading font-bold text-brand-text text-sm tracking-[0.15em] uppercase">
            Clendan
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden lg:flex items-center gap-6">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors uppercase tracking-wider"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* CTAs */}
        <div className="hidden lg:flex items-center gap-3">
          <Link
            href="#"
            className="text-xs font-mono text-brand-muted hover:text-brand-text border border-brand-border px-4 py-2 rounded-sm transition-colors"
          >
            View Docs
          </Link>
          <Link
            href="#"
            className="text-xs font-mono bg-brand-green text-black px-4 py-2 rounded-sm font-semibold hover:bg-[#00a844] transition-colors active:scale-[0.97]"
          >
            Request Access
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="lg:hidden text-brand-muted hover:text-brand-text transition-colors"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="lg:hidden border-t border-brand-border bg-brand-bg px-6 py-4 flex flex-col gap-4">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-mono text-brand-muted hover:text-brand-text transition-colors uppercase tracking-wider"
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          <div className="flex flex-col gap-2 pt-2 border-t border-brand-border">
            <Link href="#" className="text-sm font-mono text-brand-muted border border-brand-border px-4 py-2 rounded-sm text-center">
              View Docs
            </Link>
            <Link href="#" className="text-sm font-mono bg-brand-green text-black px-4 py-2 rounded-sm font-semibold text-center">
              Request Access
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
