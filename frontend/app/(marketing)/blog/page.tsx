import Link from 'next/link'

const POSTS = [
  {
    title: 'Why 66% of AP teams are still manually processing invoices in 2025',
    excerpt:
      'Despite decades of automation promises, accounts payable remains stubbornly manual. Here\'s what\'s blocking progress - and how AI is finally changing it.',
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

export const metadata = {
  title: 'Blog - Clendan',
  description: 'Practical guides, product updates, and research for finance teams.',
}

export default function BlogPage() {
  return (
    <div className="bg-brand-bg text-brand-text">
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-14">
        <p className="font-body text-[11px] uppercase tracking-widest text-brand-muted mb-4">
          Blog
        </p>
        <h1
          className="text-4xl md:text-5xl font-heading font-extrabold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          Finance Automation Insights
        </h1>
        <p className="font-body text-sm text-brand-secondary max-w-xl">
          Practical guides, product updates, and research for finance teams.
        </p>
      </section>

      {/* Posts grid */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pb-24">
        <div className="grid md:grid-cols-3 gap-4">
          {POSTS.map((post) => (
            <article
              key={post.slug}
              className="bg-brand-surface border border-brand-border rounded-sm p-6 flex flex-col gap-4"
            >
              <div className="flex items-center justify-between">
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
              </div>

              <div className="flex flex-col gap-2 flex-1">
                <h2
                  className="font-heading font-bold text-base leading-snug"
                  style={{ fontFamily: 'var(--font-heading)' }}
                >
                  {post.title}
                </h2>
                <p className="font-body text-xs text-brand-secondary leading-relaxed">
                  {post.excerpt}
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-brand-border">
                <span className="text-[11px] font-body text-brand-muted">
                  {formatDate(post.date)}
                </span>
                <Link
                  href={`/blog/${post.slug}`}
                  className="text-xs font-body text-brand-green hover:text-brand-text transition-colors"
                >
                  Read more →
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
