import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  type AuditFilters,
  type HitlAction,
  type Job,
  type ProfileUpdate,
} from "@/lib/api";

export const queryKeys = {
  jobs: ["jobs"] as const,
  job: (id: string) => ["jobs", id] as const,
  audit: (filters: AuditFilters, offset = 0) => ["audit", filters, offset] as const,
  profile: ["profile"] as const,
  masterResume: ["masterResume"] as const,
  backups: ["backups"] as const,
  trends: ["trends"] as const,
  upskill: ["upskill"] as const,
  pending: ["pending"] as const,
  applications: (status?: string) => ["applications", status ?? "all"] as const,
  application: (jobId: string) => ["application", jobId] as const,
  runs: ["runs"] as const,
  run: (id: string) => ["runs", id] as const,
  settings: ["settings"] as const,
};

// --- Jobs ---

export function useJobsQuery() {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: api.jobs,
  });
}

export function useJobQuery(id: string) {
  return useQuery({
    queryKey: queryKeys.job(id),
    queryFn: () => api.job(id),
    enabled: Boolean(id),
  });
}

export function usePruneJobsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.pruneJobs,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
    },
  });
}

export function usePruneJobMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.pruneJob(id),
    onSuccess: (_data, id) => {
      queryClient.setQueryData<Job[]>(queryKeys.jobs, (current) =>
        current ? current.filter((j) => j.id !== id) : [],
      );
    },
  });
}

// --- Audit ---

export function useAuditQuery(filters: AuditFilters = {}, offset = 0) {
  return useQuery({
    queryKey: queryKeys.audit(filters, offset),
    queryFn: () => api.audit(filters, offset),
  });
}

// --- Profile ---

export function useProfileQuery() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: api.profile,
  });
}

export function useMasterResumeQuery() {
  return useQuery({
    queryKey: queryKeys.masterResume,
    queryFn: api.exportMaster,
  });
}

export function useBackupsQuery() {
  return useQuery({
    queryKey: queryKeys.backups,
    queryFn: api.backups,
  });
}

export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: ProfileUpdate) => api.updateProfile(update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
      queryClient.invalidateQueries({ queryKey: queryKeys.masterResume });
      queryClient.invalidateQueries({ queryKey: queryKeys.backups });
    },
  });
}

export function useRestoreBackupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.restoreBackup(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
      queryClient.invalidateQueries({ queryKey: queryKeys.masterResume });
      queryClient.invalidateQueries({ queryKey: queryKeys.backups });
    },
  });
}

export function useValidateProfileMutation() {
  return useMutation({
    mutationFn: api.validateProfile,
  });
}

export function useQueryScreeningMutation() {
  return useMutation({
    mutationFn: (question: string) => api.queryScreening(question),
  });
}

export function useAddBulletMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ roleId, text, skills }: { roleId: string; text: string; skills?: string[] }) =>
      api.addBullet(roleId, text, skills ?? []),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
      queryClient.invalidateQueries({ queryKey: queryKeys.masterResume });
    },
  });
}

// --- Analytics ---

export function useTrendsQuery() {
  return useQuery({
    queryKey: queryKeys.trends,
    queryFn: api.trends,
  });
}

export function useUpskillQuery() {
  return useQuery({
    queryKey: queryKeys.upskill,
    queryFn: api.upskill,
  });
}

// --- HITL ---

export function usePendingApplicationsQuery() {
  return useQuery({
    queryKey: queryKeys.pending,
    queryFn: api.pending,
  });
}

export function useApplicationsQuery(status?: string) {
  return useQuery({
    queryKey: queryKeys.applications(status),
    queryFn: () => api.applications(status),
  });
}

export function useApplicationQuery(jobId: string) {
  return useQuery({
    queryKey: queryKeys.application(jobId),
    queryFn: () => api.application(jobId),
    enabled: Boolean(jobId),
  });
}

export function useHitlActionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, action }: { jobId: string; action: HitlAction }) =>
      api.hitl(jobId, action),
    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.pending });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.application(jobId) });
    },
  });
}

export function useSubmitAnswersMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, answers }: { jobId: string; answers: Record<string, string> }) =>
      api.answer(jobId, answers),
    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.pending });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.application(jobId) });
    },
  });
}

// --- Commands & Runs ---

export function useRunsQuery() {
  return useQuery({
    queryKey: queryKeys.runs,
    queryFn: api.runs,
  });
}

export function useRunQuery(id: string) {
  return useQuery({
    queryKey: queryKeys.run(id),
    queryFn: () => api.getRun(id),
    enabled: Boolean(id),
  });
}

export function useLaunchCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, params }: { name: string; params?: Record<string, unknown> }) =>
      api.launchCommand(name, params ?? {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}

export function useCancelRunMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.cancelRun(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}

// --- Settings ---

export function useSettingsQuery() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: api.settings,
  });
}
