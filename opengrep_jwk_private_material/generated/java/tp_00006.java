import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"EC","kid":"zgCSNhf6O2SN","alg":"ES256","crv":"P-256","x":"rPFCBxfbKIlJWD5BpIe2GgQGZBMhu1f14OGRqafaJe7","y":"0Fc3xKiNa-7i9tvWOBwPpPm_iDj6nuzAMMZ2iD5DV7a","d":"rvg133LLTmAskeuQmE3G89GI24h8PZTgEpvDfb5amu-mGAc--46jIEcOrD9GdHt8"}
    String jwk = "{\"kty\":\"EC\",\"kid\":\"zgCSNhf6O2SN\",\"alg\":\"ES256\",\"crv\":\"P-256\",\"x\":\"rPFCBxfbKIlJWD5BpIe2GgQGZBMhu1f14OGRqafaJe7\",\"y\":\"0Fc3xKiNa-7i9tvWOBwPpPm_iDj6nuzAMMZ2iD5DV7a\",\"d\":\"rvg133LLTmAskeuQmE3G89GI24h8PZTgEpvDfb5amu-mGAc--46jIEcOrD9GdHt8\"}";
    JWK.parse(jwk);
  }
}
