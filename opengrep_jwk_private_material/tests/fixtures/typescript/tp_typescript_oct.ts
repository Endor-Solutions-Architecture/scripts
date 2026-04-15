import { importJWK } from "jose";

const symmetricJwk = {
  kty: "oct",
  kid: "symm-1",
  alg: "HS256",
  k: "c2VjcmV0LXNlZWQtbWF0ZXJpYWwtd2l0aC1lbm91Z2gtbGVuZ3Ro"
};

void importJWK(symmetricJwk, "HS256");
