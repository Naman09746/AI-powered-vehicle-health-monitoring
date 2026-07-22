"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { historyApi } from "@/lib/api";
import { useToast } from "@/store/toastStore";
import { motion, AnimatePresence } from "framer-motion";
import { History, Wrench, Trash2, Plus, Calendar, DollarSign, PenTool, X } from "lucide-react";
import { cn } from "@/lib/utils";

export default function HistoryPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const toast = useToast();
  const queryClient = useQueryClient();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    service_date: new Date().toISOString().split("T")[0],
    service_type: "",
    parts_replaced: "",
    cost: "",
    notes: "",
  });

  const { data: records, isLoading } = useQuery({
    queryKey: ["history", vehicleId],
    queryFn: () => historyApi.list(vehicleId).then((r) => r.data),
    enabled: !!vehicleId,
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => historyApi.create(vehicleId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["history", vehicleId] });
      toast.add("Maintenance record added", "success");
      setForm({
        service_date: new Date().toISOString().split("T")[0],
        service_type: "",
        parts_replaced: "",
        cost: "",
        notes: "",
      });
      setShowForm(false);
    },
    onError: () => {
      toast.add("Failed to add record", "error");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (recordId: number) => historyApi.delete(vehicleId, recordId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["history", vehicleId] });
      toast.add("Maintenance record deleted", "success");
    },
    onError: () => {
      toast.add("Failed to delete record", "error");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.service_type.trim()) {
      toast.add("Service type is required", "error");
      return;
    }
    createMutation.mutate({
      ...form,
      cost: form.cost ? Number(form.cost) : null,
      parts_replaced: form.parts_replaced.trim() || null,
      notes: form.notes.trim() || null,
    });
  };

  const handleDelete = (recordId: number) => {
    if (confirm("Are you sure you want to delete this record?")) {
      deleteMutation.mutate(recordId);
    }
  };

  if (isLoading) return <LoadingSpinner size="lg" />;

  const recordList = Array.isArray(records) ? records : [];

  return (
    <div>
      <PageHeader
        title="Maintenance History"
        description={`${recordList.length} service record${recordList.length !== 1 ? "s" : ""} registered`}
        actions={
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-primary flex items-center gap-2"
          >
            {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
            {showForm ? "Cancel" : "Add Record"}
          </button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Add Record Form */}
        <AnimatePresence>
          {showForm && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="lg:col-span-1 glass-card p-5 space-y-4"
            >
              <h3 className="font-heading font-semibold text-text-primary text-sm flex items-center gap-2">
                <PenTool className="w-4 h-4 text-accent-sky" />
                New Service Record
              </h3>
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label htmlFor="service_date" className="block text-xs text-text-muted mb-1 font-medium">Service Date</label>
                  <input
                    id="service_date"
                    type="date"
                    className="input-field"
                    value={form.service_date}
                    onChange={(e) => setForm({ ...form, service_date: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="service_type" className="block text-xs text-text-muted mb-1 font-medium">Service / Repair Type *</label>
                  <input
                    id="service_type"
                    type="text"
                    placeholder="e.g. Engine Oil Change"
                    className="input-field"
                    value={form.service_type}
                    onChange={(e) => setForm({ ...form, service_type: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="parts_replaced" className="block text-xs text-text-muted mb-1 font-medium">Parts Replaced (optional)</label>
                  <input
                    id="parts_replaced"
                    type="text"
                    placeholder="e.g. Oil Filter, Spark plugs"
                    className="input-field"
                    value={form.parts_replaced}
                    onChange={(e) => setForm({ ...form, parts_replaced: e.target.value })}
                  />
                </div>
                <div>
                  <label htmlFor="cost" className="block text-xs text-text-muted mb-1 font-medium">Cost ($)</label>
                  <input
                    id="cost"
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    className="input-field"
                    value={form.cost}
                    onChange={(e) => setForm({ ...form, cost: e.target.value })}
                  />
                </div>
                <div>
                  <label htmlFor="notes" className="block text-xs text-text-muted mb-1 font-medium">Notes (optional)</label>
                  <textarea
                    id="notes"
                    placeholder="Additional details..."
                    rows={3}
                    className="input-field resize-none"
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  />
                </div>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="btn-primary w-full mt-2"
                >
                  {createMutation.isPending ? "Saving..." : "Save Record"}
                </button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>

        {/* History List */}
        <div className={cn("space-y-3", showForm ? "lg:col-span-2" : "lg:col-span-3")}>
          {recordList.length === 0 ? (
            <EmptyState
              icon={<History className="w-16 h-16" />}
              title="No records registered"
              description="Keep track of repairs, replacements, and services to optimize predictive models."
            />
          ) : (
            <div className="space-y-3">
              {recordList.map((r: any, i: number) => (
                <motion.div
                  key={r.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="glass-card p-4 flex items-start justify-between gap-4"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg bg-accent-amber/10 flex items-center justify-center flex-shrink-0 mt-1">
                      <Wrench className="w-5 h-5 text-accent-amber" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-heading font-semibold text-text-primary text-sm">
                        {r.service_type}
                      </h4>
                      <div className="flex items-center gap-3 text-xs text-text-muted mt-1.5 flex-wrap">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {r.service_date ? new Date(r.service_date).toLocaleDateString() : "—"}
                        </span>
                        {r.cost != null && (
                          <span className="flex items-center gap-0.5 font-medium text-text-primary">
                            <DollarSign className="w-3.5 h-3.5 text-accent-green" />
                            {r.cost.toFixed(2)}
                          </span>
                        )}
                      </div>
                      {r.parts_replaced && (
                        <p className="text-xs text-text-muted mt-2 bg-base-surface/40 px-2 py-1 rounded border border-border/20 inline-block">
                          Parts: <span className="text-text-primary">{r.parts_replaced}</span>
                        </p>
                      )}
                      {r.notes && (
                        <p className="text-xs text-text-muted mt-2 leading-relaxed">
                          {r.notes}
                        </p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(r.id)}
                    disabled={deleteMutation.isPending}
                    className="btn-ghost p-1.5 rounded-lg text-text-muted hover:text-accent-red hover:bg-accent-red/5 self-center"
                    aria-label={`Delete record for ${r.service_type}`}
                  >
                    <Trash2 className="w-4.5 h-4.5" />
                  </button>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
