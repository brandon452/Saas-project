'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'

import { getApiErrorMessage } from '@/lib/api'
import { usePasswordSetTokenDetail, useSetPassword } from '@/lib/hooks/useCreateUser'

export default function SetPasswordPage() {
  const params = useParams()
  const token = typeof params.token === 'string' ? params.token : ''
  const router = useRouter()

  const { data, isLoading, isError } = usePasswordSetTokenDetail(token)

  const setPassword = useSetPassword(token)

  const [password, setPasswordValue] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [clientError, setClientError] = useState<string | null>(null)

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setClientError(null)

    if (password !== confirm) {
      setClientError('Passwords do not match.')
      return
    }

    setPassword.mutate(
      { password },
      {
        onSuccess: () => {
          router.push('/')
        },
        onError: (err: unknown) => {
          setClientError(getApiErrorMessage(err, 'Something went wrong. Please try again.'))
        },
      },
    )
  }

  const contextLine = (() => {
    if (!data) return null
    if (data.org_name) return `You've been invited to ${data.org_name}.`
    if (data.parent_role === 'PARENT_ADMIN') return "You've been set up as a Parent Admin."
    if (data.parent_role === 'PARENT_VIEWER') return "You've been set up as a Parent Viewer."
    return null
  })()

  return (
    <main className='flex min-h-screen items-center justify-center bg-[#F9FAFB] px-4'>
      <div className='w-full max-w-sm'>
        <div className='mb-8 text-center'>
          <h1 className='text-3xl font-bold tracking-tight text-[#111827]'>Symbiosis</h1>
          <p className='mt-2 text-sm text-[#6B7280]'>Internal Inventory System</p>
        </div>

        <div className='rounded-2xl border border-[#E5E7EB] bg-white p-8 shadow-sm'>
          {isLoading ? (
            <p className='text-center text-sm text-[#6B7280]'>Loading&hellip;</p>
          ) : isError ? (
            <div className='text-center'>
              <p className='text-sm font-medium text-[#111827]'>This link is invalid or has expired.</p>
              <p className='mt-1 text-sm text-[#6B7280]'>Ask an admin to generate a new invite link.</p>
            </div>
          ) : (
            <>
              <div className='mb-6'>
                <p className='text-sm font-medium text-[#111827]'>
                  Hi {data?.first_name},
                </p>
                {contextLine && (
                  <p className='mt-0.5 text-sm text-[#6B7280]'>{contextLine}</p>
                )}
                <p className='mt-1 text-sm text-[#6B7280]'>Set a password to activate your account.</p>
              </div>

              <form onSubmit={handleSubmit} className='space-y-5'>
                <div>
                  <label htmlFor='password' className='mb-1.5 block text-sm font-medium text-[#374151]'>
                    Password
                  </label>
                  <div className='relative'>
                    <input
                      id='password'
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete='new-password'
                      value={password}
                      onChange={(e) => setPasswordValue(e.target.value)}
                      className='w-full rounded-lg border border-[#D1D5DB] bg-white px-3 py-2.5 pr-10 text-sm text-[#111827] placeholder-[#9CA3AF] outline-none transition-colors duration-150 focus:border-[#111827] focus:ring-1 focus:ring-[#111827]'
                    />
                    <button
                      type='button'
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className='absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#111827] focus:outline-none'
                    >
                      {showPassword ? (
                        <svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round'>
                          <path d='M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94' />
                          <path d='M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19' />
                          <line x1='1' y1='1' x2='23' y2='23' />
                        </svg>
                      ) : (
                        <svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round'>
                          <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' />
                          <circle cx='12' cy='12' r='3' />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor='confirm' className='mb-1.5 block text-sm font-medium text-[#374151]'>
                    Confirm Password
                  </label>
                  <div className='relative'>
                    <input
                      id='confirm'
                      type={showConfirm ? 'text' : 'password'}
                      required
                      autoComplete='new-password'
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      className='w-full rounded-lg border border-[#D1D5DB] bg-white px-3 py-2.5 pr-10 text-sm text-[#111827] placeholder-[#9CA3AF] outline-none transition-colors duration-150 focus:border-[#111827] focus:ring-1 focus:ring-[#111827]'
                    />
                    <button
                      type='button'
                      onClick={() => setShowConfirm((v) => !v)}
                      aria-label={showConfirm ? 'Hide password' : 'Show password'}
                      className='absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#111827] focus:outline-none'
                    >
                      {showConfirm ? (
                        <svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round'>
                          <path d='M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94' />
                          <path d='M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19' />
                          <line x1='1' y1='1' x2='23' y2='23' />
                        </svg>
                      ) : (
                        <svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round'>
                          <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' />
                          <circle cx='12' cy='12' r='3' />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {(clientError ?? setPassword.error) && (
                  <p role='alert' className='rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]'>
                    {clientError ?? getApiErrorMessage(setPassword.error, 'Something went wrong.')}
                  </p>
                )}

                <button
                  type='submit'
                  disabled={setPassword.isPending}
                  className='w-full rounded-lg bg-[#111827] px-4 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#111827] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70'
                >
                  {setPassword.isPending ? 'Setting password...' : 'Set Password'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </main>
  )
}
