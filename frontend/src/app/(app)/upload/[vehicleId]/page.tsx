"use client";

import { useParams } from "next/navigation";
import { useState, useCallback } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useDropzone } from "react-dropzone";
import { uploadApi } from "@/lib/api";
import { useToast } from "@/store/toastStore";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Upload, FileText, Download, CheckCircle, AlertCircle, Brain, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { NextStepCard } from "@/components/shared/NextStepCard";

export default function UploadPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadedSuccessfully, setUploadedSuccessfully] = useState(false);
  const { data: uploads, isLoading, refetch } = useQuery({ queryKey: ["uploads", vehicleId], queryFn: () => uploadApi.history(vehicleId).then((r) => r.data), enabled: !!vehicleId });

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    if (!file.name.endsWith(".csv")) { toast.add("Only CSV files are supported", "error"); return; }
    setUploading(true); setProgress(0); setUploadedSuccessfully(false);
    try {
      await uploadApi.upload(vehicleId, file, setProgress);
      toast.add(`Uploaded ${file.name}`, "success");
      setUploadedSuccessfully(true);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["dashboard", vehicleId] });
      queryClient.invalidateQueries({ queryKey: ["fleet"] });
    } catch { toast.add("Upload failed", "error"); }
    finally { setUploading(false); }
  }, [vehicleId, toast, refetch, queryClient]);

  const handleDeleteUpload = useCallback(async (uploadId: number) => {
    if (!confirm("Are you sure you want to delete this upload? This will also remove all associated readings from the charts.")) return;
    try {
      await uploadApi.delete(uploadId);
      toast.add("Upload deleted", "success");
      refetch();
      queryClient.invalidateQueries({ queryKey: ["dashboard", vehicleId] });
      queryClient.invalidateQueries({ queryKey: ["fleet"] });
    } catch {
      toast.add("Failed to delete upload", "error");
    }
  }, [vehicleId, toast, refetch, queryClient]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/vnd.ms-excel": [".csv"],
      "text/comma-separated-values": [".csv"],
    },
    maxFiles: 1,
    disabled: uploading
  });

  const handleDownloadSample = async () => {
    try {
      const response = await uploadApi.sampleCsv();
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `sample_vehicle_${vehicleId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      toast.add("Sample CSV downloaded", "success");
    } catch {
      toast.add("Download failed", "error");
    }
  };

  return (
    <div>
      <PageHeader title="Upload Data" description="Upload CSV sensor data for analysis" />
      <div {...getRootProps()} className={cn("glass-card p-12 text-center cursor-pointer transition-all duration-200 mb-6", isDragActive && "border-accent-sky/50 shadow-glow", uploading && "opacity-50 pointer-events-none")}>
        <input {...getInputProps()} aria-label="Upload CSV file" />
        <Upload className="w-12 h-12 mx-auto mb-4 text-text-muted/40" aria-hidden="true" />
        {uploading ? (
          <div><p className="text-text-muted mb-2">Uploading... {progress}%</p><div className="w-48 h-1.5 bg-base-elevated rounded-full mx-auto overflow-hidden"><div className="h-full bg-accent-sky rounded-full transition-all" style={{ width: `${progress}%` }} /></div></div>
        ) : isDragActive ? (
          <p className="text-accent-sky font-medium">Drop CSV here</p>
        ) : (
          <div><p className="text-text-primary font-medium mb-1">Drag & drop CSV or click to browse</p><p className="text-text-muted text-sm">Sensor readings with columns: timestamp, engine_temp, oil_pressure, etc.</p></div>
        )}
      </div>
      <div className="flex gap-3 mb-6">
        <button onClick={handleDownloadSample} className="btn-secondary text-sm flex items-center gap-2"><Download className="w-4 h-4" /> Sample CSV</button>
      </div>

      {uploadedSuccessfully && (
        <NextStepCard
          title="Telemetry Data Uploaded Successfully"
          description="Your sensor data has been uploaded and parsed. The next step is to train a machine learning model using this data to identify patterns and predict future failures."
          href={`/training/${vehicleId}`}
          actionLabel="Go to ML Training"
          icon={Brain}
        />
      )}

      {isLoading ? <LoadingSpinner size="sm" /> : uploads && uploads.length > 0 && (
        <div className="glass-card p-5 mt-6"><h3 className="font-heading font-semibold text-text-primary mb-3">Upload History</h3>
          <div className="space-y-2">{(uploads as Array<{id:number;filename:string;row_count_raw:number;row_count_clean:number;upload_time:string}>).map((u) => (
            <div key={u.id} className="flex items-center justify-between p-3 rounded-lg bg-base-elevated/50">
              <div className="flex items-center gap-3"><FileText className="w-4 h-4 text-text-muted" /><span className="text-sm text-text-primary">{u.filename}</span><span className="text-xs text-text-muted">{u.row_count_raw ?? "—"} rows</span></div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-text-muted">{u.upload_time ? new Date(u.upload_time).toLocaleDateString() : ""}</span>
                <button
                  onClick={() => handleDeleteUpload(u.id)}
                  className="text-text-muted hover:text-red-500 transition-colors p-1 rounded-md hover:bg-red-500/10"
                  title="Delete Upload"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}</div>
        </div>
      )}
    </div>
  );
}
