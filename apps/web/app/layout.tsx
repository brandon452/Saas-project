import './globals.css'

import type { Metadata } from 'next'
import { ReactNode } from 'react'

import { Providers } from './providers'

export const metadata: Metadata = {
  title: 'Inventory Web',
  description: 'Multi-tenant inventory web app',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
