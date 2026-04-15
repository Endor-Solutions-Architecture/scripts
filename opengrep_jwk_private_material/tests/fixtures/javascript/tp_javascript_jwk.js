import { importJWK } from "jose";

const privateJwk = {
  kty: "EC",
  crv: "P-256",
  x: "f83OJ3D2xF4k6YfLJ5L4",
  y: "x_FEzRu9Vf2A0n7jPVzG",
  d: "jY9aNnqM2JX0aWQYh8x8F3Vn4z8QnKx1"
};

await importJWK(privateJwk, "ES256");
