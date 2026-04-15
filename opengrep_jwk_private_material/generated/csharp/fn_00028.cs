using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"YVwblfqFuBKl","alg":"RS256","n":"k4z87iT-vFiH-mfoBta1J2tgAWetsjwGRg4MRSjQ53CfLYFb","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"YVwblfqFuBKl\",\"alg\":\"RS256\",\"n\":\"k4z87iT-vFiH-mfoBta1J2tgAWetsjwGRg4MRSjQ53CfLYFb\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
