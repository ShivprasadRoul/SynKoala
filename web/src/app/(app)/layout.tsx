"use client";

import Link from "next/link";

import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/providers/AuthProvider";

function TopNav() {
  const { session, signOut } = useAuth();
  return (
    <header className="border-b border-hairline bg-canvas">
      <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-6">
        <Link href="/dashboard" className="font-display text-[16px] font-extrabold text-ink">
          SynKoala Studio
        </Link>
        <div className="flex items-center gap-4">
          {session?.user.email && (
            <span className="text-[13px] text-ink-muted">{session.user.email}</span>
          )}
          <button
            onClick={() => signOut()}
            className="text-[13px] font-semibold text-ink-muted hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <TopNav />
      <main className="mx-auto max-w-[1180px] px-6 py-10">{children}</main>
    </AuthGuard>
  );
}
