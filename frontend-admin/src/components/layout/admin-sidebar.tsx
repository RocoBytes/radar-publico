"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Users, LogOut, LayoutDashboard, DollarSign } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type AdminSidebarProps = {
  email: string;
};

const navItems = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
  },
  {
    href: "/costos-ia",
    label: "Costos IA",
    icon: DollarSign,
  },
  {
    href: "/cuentas",
    label: "Cuentas",
    icon: Users,
  },
];

export function AdminSidebar({ email }: AdminSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    router.push("/login");
  }

  return (
    <aside className="flex h-screen w-60 flex-col border-r bg-background">
      {/* Logo */}
      <div className="flex items-center gap-2 border-b px-4 py-4">
        <span className="font-semibold text-sm leading-tight">
          Radar Público
        </span>
        <Badge variant="secondary" className="text-xs">
          admin
        </Badge>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-3 space-y-2">
        <p className="truncate text-xs text-muted-foreground px-1">{email}</p>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-muted-foreground hover:text-destructive"
          onClick={() => void handleLogout()}
        >
          <LogOut className="h-4 w-4" />
          Cerrar sesión
        </Button>
      </div>
    </aside>
  );
}
