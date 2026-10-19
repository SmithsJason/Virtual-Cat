import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { cats } from "../lib/cats";

export function LoginCat() {
  const [petted, setPetted] = useState(false);

  useEffect(() => {
    if (!petted) return;
    const timer = setTimeout(() => setPetted(false), 1300);
    return () => clearTimeout(timer);
  }, [petted]);

  return (
    <div className="auth-cat" data-petted={petted}>
      <div className="auth-orbit" aria-hidden="true" />
      <div className="auth-cat-shadow" aria-hidden="true" />
      <button
        type="button"
        className="auth-cat-pet"
        aria-label="摸摸小猫"
        title="摸摸我吧"
        onClick={() => setPetted(true)}
      >
        <img
          src={cats.calico.image}
          alt="等待与你相遇的三花小猫"
          draggable={false}
        />
      </button>
      <span className="auth-cat-heart heart-one" aria-hidden="true">
        <Heart size={17} />
      </span>
      <span className="auth-cat-heart heart-two" aria-hidden="true">
        <Heart size={12} />
      </span>
      <span className="auth-cat-heart heart-three" aria-hidden="true">
        <Heart size={14} />
      </span>
      <span className="floating-note" role="status">
        <Heart size={16} /> {petted ? "呼噜呼噜，好喜欢你" : "今天也在等你"}
      </span>
      <span className="auth-cat-invitation" aria-hidden="true">
        轻轻摸摸我，打个招呼吧
      </span>
    </div>
  );
}
