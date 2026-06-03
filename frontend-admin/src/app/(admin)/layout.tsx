import { redirect } from "next/navigation";
import { getAdminUser } from "@/lib/auth";
import { AdminSidebar } from "@/components/layout/admin-sidebar";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getAdminUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <AdminSidebar email={user.email} />
      <main className="flex-1 overflow-y-auto bg-muted/20 p-6">
        {children}
      </main>
    </div>
  );
}
