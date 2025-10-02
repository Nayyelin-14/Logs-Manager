import { InputOTPForm } from "../../AppComponents/Forms/OtpForm";
import { useEffect } from "react";
import { toast } from "sonner";
import useAuthStore from "../../store/authStore";

export default function OtpPage() {
  const message = useAuthStore((state) => state.message);

  useEffect(() => {
    if (message) {
      toast.success(message);
    }
  }, [message]);
  return (
    <div className=" flex items-center justify-center min-h-[600px]">
      <div className="w-full max-w-sm">
        <InputOTPForm />
      </div>
    </div>
  );
}
