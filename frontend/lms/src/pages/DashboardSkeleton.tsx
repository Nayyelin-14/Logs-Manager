import { Skeleton } from "../components/ui/skeleton";

const DashboardSkeleton = ({ variant = "overview" }: { variant?: "overview" | "analytics" }) => (
  <div className="space-y-5">
    <div className="border-b border-border pb-5">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="mt-3 h-8 w-64" />
      <Skeleton className="mt-3 h-4 w-full max-w-xl" />
    </div>
    {variant === "overview" ? <>
      <div className="grid gap-4 xl:grid-cols-12"><Skeleton className="h-[380px] rounded-md xl:col-span-8" /><Skeleton className="h-[380px] rounded-md xl:col-span-4" /></div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12"><Skeleton className="h-56 rounded-md xl:col-span-5" /><Skeleton className="h-56 rounded-md xl:col-span-4" /><Skeleton className="h-56 rounded-md xl:col-span-3" /></div>
      <div className="grid gap-4 xl:grid-cols-12"><Skeleton className="h-[440px] rounded-md xl:col-span-8" /><Skeleton className="h-[260px] rounded-md xl:col-span-4" /></div>
    </> : <>
      <div className="grid gap-4 xl:grid-cols-12"><Skeleton className="h-[370px] rounded-md xl:col-span-8" /><Skeleton className="h-[370px] rounded-md xl:col-span-4" /></div>
      <div className="grid gap-4 xl:grid-cols-12"><Skeleton className="h-64 rounded-md xl:col-span-8" /><Skeleton className="h-64 rounded-md xl:col-span-4" /></div>
      <div className="grid gap-4 xl:grid-cols-12"><Skeleton className="h-64 rounded-md xl:col-span-5" /><Skeleton className="h-64 rounded-md xl:col-span-7" /></div>
    </>}
  </div>
);

export default DashboardSkeleton;
