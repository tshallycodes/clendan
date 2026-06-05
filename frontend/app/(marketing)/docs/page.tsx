import { redirect } from 'next/navigation'

export const metadata = {
  title: 'Documentation — Clendan',
}

export default function DocsPage() {
  redirect('https://docs.clendan.com')
}
