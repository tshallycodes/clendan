import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isPublicRoute = createRouteMatcher([
  '/',
  '/how-it-works',
  '/workers',
  '/api-tools',
  '/integrations',
  '/pricing',
  '/about',
  '/blog(.*)',
  '/changelog',
  '/security',
  '/privacy',
  '/terms',
  '/security-policy',
  '/sign-in(.*)',
  '/sign-up(.*)',
])

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect()
  }
})

export const config = {
  matcher: ['/((?!.+\\.[\\w]+$|_next).*)', '/', '/(api|trpc)(.*)'],
}
