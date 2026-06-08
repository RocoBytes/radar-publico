"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { getMeClient } from "@/lib/api"

export function AuthGuard() {
  const router = useRouter()
  const { data: user, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: getMeClient,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (isLoading || !user) return
    if (user.must_change_password) {
      router.replace("/change-password")
      return
    }
    if (!user.empresa?.onboarding_completado) {
      router.replace("/onboarding")
    }
  }, [user, isLoading, router])

  return null
}
