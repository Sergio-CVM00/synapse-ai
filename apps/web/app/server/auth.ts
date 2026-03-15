import { createServerFn } from '@tanstack/react-start'
import { createServerSupabaseClient } from '~/lib/supabase.server'
import { z } from 'zod'

const SignUpData = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})

const SignInData = z.object({
  email: z.string().email(),
  password: z.string().min(1),
})

export const signUp = createServerFn({ method: 'POST' })
  .handler(async ({ data }) => {
    const validated = SignUpData.parse(data)
    const supabase = createServerSupabaseClient()
    const { error } = await supabase.auth.signUp({
      email: validated.email,
      password: validated.password,
    })
    if (error) throw error
    return { success: true }
  })

export const signIn = createServerFn({ method: 'POST' })
  .handler(async ({ data }) => {
    const validated = SignInData.parse(data)
    const supabase = createServerSupabaseClient()
    const { error } = await supabase.auth.signInWithPassword({
      email: validated.email,
      password: validated.password,
    })
    if (error) throw error
    return { success: true }
  })

export const signOut = createServerFn({ method: 'POST' }).handler(async () => {
  const supabase = createServerSupabaseClient()
  const { error } = await supabase.auth.signOut()
  if (error) throw error
  return { success: true }
})

export const getSession = createServerFn({ method: 'GET' }).handler(async () => {
  const supabase = createServerSupabaseClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session
})
