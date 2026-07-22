"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { reportApi } from "@/lib/api";
import { useToast } from "@/store/toastStore";
import { FileText, Download } from "lucide-react";

export default function ReportsPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    setLoading(true);
    try { await reportApi.pdf(vehicleId); toast.add("Report downloaded", "success"); }
    catch { toast.add("Report generation failed", "error"); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <PageHeader title="Reports" description="Generate PDF vehicle health reports" />
      <div className="glass-card p-8 text-center max-w-lg mx-auto">
        <div className="w-16 h-16 rounded-xl bg-accent-sky/10 flex items-center justify-center mx-auto mb-4"><FileText className="w-8 h-8 text-accent-sky" /></div>
        <h2 className="text-lg font-heading font-semibold text-text-primary mb-2">Vehicle Health Report</h2>
        <p className="text-sm text-text-muted mb-6">Generate a comprehensive PDF report with sensor trends, health score, predictions, and maintenance history.</p>
        <button onClick={handleDownload} disabled={loading} className="btn-primary flex items-center gap-2 mx-auto">
          <Download className="w-4 h-4" />{loading ? "Generating..." : "Download PDF Report"}
        </button>
      </div>
    </div>
  );
}
