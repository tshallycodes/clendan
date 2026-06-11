import { NextResponse } from 'next/server'
import type { NextFetchEvent, NextRequest } from 'next/server'

// Conditionally load Clerk only when a valid publishable key is present.
// This allows the dev server to run without Clerk keys configured,
// while production (with real keys) gets full Clerk auth enforcement.
function createClerkHandler() {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? ''
  if (!key.startsWith('pk_test_') && !key.startsWith('pk_live_')) {
    return null
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { clerkMiddleware, createRouteMatcher } = require('@clerk/nextjs/server') as typeof import('@clerk/nextjs/server')
  const isPublicRoute = createRouteMatcher([
    '/',
    '/sign-in(.*)',
    '/sign-up(.*)',
    '/about(.*)',
    '/pricing(.*)',
    '/blog(.*)',
    '/changelog(.*)',
    '/docs(.*)',
    '/how-it-works(.*)',
    '/integrations(.*)',
    '/tools(.*)',
    '/security(.*)',
    '/privacy(.*)',
    '/terms(.*)',
    '/security-policy(.*)',
    '/maintenance(.*)',
    '/api-tools(.*)',
  ])
  return clerkMiddleware((auth, request) => {
    if (!isPublicRoute(request)) {
      auth.protect()
    }
  })
}

const clerkHandler = createClerkHandler()

export function proxy(request: NextRequest, event: NextFetchEvent) {
  if (clerkHandler) {
    return clerkHandler(request, event)
  }

  // Development fallback when Clerk keys are not configured.
  // Protected paths redirect to /sign-in.
  const { pathname } = request.nextUrl
  if (pathname.startsWith('/dashboard')) {
    const url = new URL('/sign-in', request.url)
    url.searchParams.set('redirect_url', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
    '/__clerk/:path*',
  ],
}
