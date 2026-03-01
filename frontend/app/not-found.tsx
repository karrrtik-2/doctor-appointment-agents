import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <p className="text-6xl font-bold text-muted-foreground/30">404</p>
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        This route doesn&apos;t exist in the platform.
      </p>
      <Button asChild variant="outline">
        <Link href="/">Back to Appointments</Link>
      </Button>
    </div>
  );
}
