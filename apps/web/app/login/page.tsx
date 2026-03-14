'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export default function LoginPage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const form = e.currentTarget
    const username = (form.elements.namedItem('username') as HTMLInputElement).value
    const password = (form.elements.namedItem('password') as HTMLInputElement).value

    try {
      const res = await fetch(`${API_BASE}/api/auth/login/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      })

      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string }
        setError(data.detail ?? 'Login failed.')
        return
      }

      router.push('/')
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className='flex min-h-screen items-center justify-center bg-[#F9FAFB] px-4'>
      <div className='w-full max-w-sm'>
        <div className='mb-8 text-center'>
          <h1 className='text-3xl font-bold tracking-tight text-[#111827]'>Symbiosis</h1>
          <p className='mt-2 text-sm text-[#6B7280]'>Internal Inventory System</p>
        </div>

        <div className='rounded-2xl border border-[#E5E7EB] bg-white p-8 shadow-sm'>
          <form onSubmit={handleLogin} className='space-y-5'>
            <div>
              <label htmlFor='username' className='mb-1.5 block text-sm font-medium text-[#374151]'>
                Username
              </label>
              <input
                id='username'
                name='username'
                type='text'
                required
                autoComplete='username'
                className='w-full rounded-lg border border-[#D1D5DB] bg-white px-3 py-2.5 text-sm text-[#111827] placeholder-[#9CA3AF] outline-none transition-colors duration-150 focus:border-[#111827] focus:ring-1 focus:ring-[#111827]'
              />
            </div>

            <div>
              <label htmlFor='password' className='mb-1.5 block text-sm font-medium text-[#374151]'>
                Password
              </label>
              <div className='relative'>
                <input
                  id='password'
                  name='password'
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete='current-password'
                  className='w-full rounded-lg border border-[#D1D5DB] bg-white px-3 py-2.5 pr-10 text-sm text-[#111827] placeholder-[#9CA3AF] outline-none transition-colors duration-150 focus:border-[#111827] focus:ring-1 focus:ring-[#111827]'
                />
                <button
                  type='button'
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className='absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#111827] focus:outline-none'
                >
                  {showPassword ? (
                    <svg
                      xmlns='http://www.w3.org/2000/svg'
                      width='16'
                      height='16'
                      viewBox='0 0 24 24'
                      fill='none'
                      stroke='currentColor'
                      strokeWidth='2'
                      strokeLinecap='round'
                      strokeLinejoin='round'
                    >
                      <path d='M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8 a18.45 18.45 0 0 1 5.06-5.94' />
                      <path d='M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8 a18.5 18.5 0 0 1-2.16 3.19' />
                      <line x1='1' y1='1' x2='23' y2='23' />
                    </svg>
                  ) : (
                    <svg
                      xmlns='http://www.w3.org/2000/svg'
                      width='16'
                      height='16'
                      viewBox='0 0 24 24'
                      fill='none'
                      stroke='currentColor'
                      strokeWidth='2'
                      strokeLinecap='round'
                      strokeLinejoin='round'
                    >
                      <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' />
                      <circle cx='12' cy='12' r='3' />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {error && (
              <p role='alert' className='rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]'>
                {error}
              </p>
            )}

            <button
              type='submit'
              disabled={loading}
              className='w-full rounded-lg bg-[#111827] px-4 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#111827] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70'
            >
              {loading ? 'Logging in...' : 'Log in'}
            </button>
          </form>
        </div>
      </div>
    </main>
  )
}
