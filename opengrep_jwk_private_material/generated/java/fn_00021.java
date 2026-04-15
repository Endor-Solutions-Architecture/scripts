import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"gJruDGUcYTvB","alg":"RS256","n":"GNTfnQEmMmWQ2qxVPpc3sE2vMGGFhd2cKwWyQviMMme_hvvX","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"gJruDGUcYTvB\",\"alg\":\"RS256\",\"n\":\"GNTfnQEmMmWQ2qxVPpc3sE2vMGGFhd2cKwWyQviMMme_hvvX\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
