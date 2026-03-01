"use client";

import { useSessionStore } from "@/lib/store/session";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function TenantSelector() {
  const tenantId = useSessionStore((s) => s.tenantId);
  const setTenantId = useSessionStore((s) => s.setTenantId);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
          Settings
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="tenant-id" className="text-xs">
            Tenant ID
          </Label>
          <Input
            id="tenant-id"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            className="h-8 text-xs"
            placeholder="default"
          />
        </div>
      </CardContent>
    </Card>
  );
}
