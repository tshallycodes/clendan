import Link from 'next/link'
import { notFound } from 'next/navigation'

const POSTS = [
  {
    title: 'Why 66% of AP teams are still manually processing invoices in 2025',
    excerpt:
      'Despite decades of automation promises, accounts payable remains stubbornly manual. Here\'s what\'s blocking progress — and how AI is finally changing it.',
    date: '2026-05-15',
    readTime: '8 min read',
    category: 'Research',
    slug: 'ap-automation-2025',
  },
  {
    title: 'How to reduce month-end close from 6 days to 2',
    excerpt:
      'Month-end close is the most reliable source of finance team burnout. We break down exactly where the time goes and how AI tools eliminate each bottleneck.',
    date: '2026-05-22',
    readTime: '6 min read',
    category: 'Guide',
    slug: 'month-end-close',
  },
  {
    title: 'What is an AI financial agent and how is it different from automation?',
    excerpt:
      'Traditional automation follows rules. AI agents reason. Here\'s the practical difference for finance operations teams.',
    date: '2026-06-01',
    readTime: '5 min read',
    category: 'Product',
    slug: 'ai-financial-agent',
  },
]

const CATEGORY_COLORS: Record<string, string> = {
  Research: 'rgba(0,168,204,0.08)',
  Guide: 'rgba(245,166,35,0.08)',
  Product: 'rgba(0,200,83,0.08)',
}

const CATEGORY_TEXT: Record<string, string> = {
  Research: '#00a8cc',
  Guide: '#f5a623',
  Product: '#00C853',
}

const CATEGORY_BORDER: Record<string, string> = {
  Research: 'rgba(0,168,204,0.2)',
  Guide: 'rgba(245,166,35,0.2)',
  Product: 'rgba(0,200,83,0.2)',
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export function generateStaticParams() {
  return POSTS.map((post) => ({ slug: post.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const post = POSTS.find((p) => p.slug === slug)
  if (!post) return { title: 'Post Not Found — Clendan' }
  return { title: `${post.title} — Clendan Blog` }
}

export default async function BlogPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const post = POSTS.find((p) => p.slug === slug)

  if (!post) {
    notFound()
  }

  return (
    <div className="bg-brand-bg text-brand-text">
      <article className="max-w-2xl mx-auto px-6 md:px-8 pt-20 pb-24">
        {/* Back */}
        <Link
          href="/blog"
          className="inline-flex items-center gap-1 font-body text-xs text-brand-muted hover:text-brand-text transition-colors mb-10"
        >
          ← Back to Blog
        </Link>

        {/* Meta */}
        <div className="flex items-center gap-3 mb-6">
          <span
            className="text-[11px] font-body uppercase tracking-widest px-2 py-0.5 rounded-sm"
            style={{
              background: CATEGORY_COLORS[post.category],
              color: CATEGORY_TEXT[post.category],
              border: `1px solid ${CATEGORY_BORDER[post.category]}`,
            }}
          >
            {post.category}
          </span>
          <span className="text-[11px] font-body text-brand-muted">{post.readTime}</span>
          <span className="text-[11px] font-body text-brand-muted">{formatDate(post.date)}</span>
        </div>

        {/* Title */}
        <h1
          className="font-heading font-extrabold text-3xl md:text-4xl leading-tight mb-10"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          {post.title}
        </h1>

        {/* Divider */}
        <div className="border-t border-brand-border mb-10" />

        {/* Body */}
        <p className="font-body text-sm text-brand-secondary leading-relaxed italic text-center mb-10">
          {post.excerpt}
        </p>

        <p className="font-body text-sm text-brand-muted text-center">
          This post is being written. Check back soon.
        </p>

        {/* CTA */}
        <div className="mt-16 pt-8 border-t border-brand-border text-center">
          <Link
            href="/sign-up"
            className="inline-block rounded-sm px-6 py-3 text-sm font-body font-medium transition-colors hover:bg-[#00a844]"
            style={{ background: '#00C853', color: '#000' }}
          >
            See how Clendan automates this →
          </Link>
        </div>
      </article>
    </div>
  )
}
