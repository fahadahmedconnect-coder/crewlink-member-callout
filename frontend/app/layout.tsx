import './globals.css'

export const metadata = {
  title: 'CrewLink - Member Callout',
  description: 'Union announcement system',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
